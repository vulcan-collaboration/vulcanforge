import sys
from collections import defaultdict
from itertools import groupby, izip_longest

from pylons import tmpl_context as c, app_globals as g
from pymongo.errors import DuplicateKeyError
from ming.odm import mapper, session, Mapper
from ming.odm.declarative import MappedClass
from vulcanforge.artifact.model import ArtifactReference, Shortlink
from vulcanforge.artifact.tasks import add_artifacts
from vulcanforge.artifact.util import iter_artifact_classes
from vulcanforge.common.exceptions import CompoundError
from vulcanforge.common.model.index import GlobalObjectReference
from vulcanforge.common.model.session import (
    solr_indexed_session,
    main_orm_session,
    project_orm_session,
    repository_orm_session,
    artifact_orm_session,
    main_doc_session,
    project_doc_session)
from vulcanforge.common.tasks.index import add_global_objs
from vulcanforge.common.util.model import chunked_find

from . import base
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.model import Project


class ShowModelsCommand(base.Command):
    min_args = 1
    max_args = 1
    usage = '<ini file>'
    summary = 'Show the inheritance graph of all Ming models'
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        graph = build_model_inheritance_graph()
        for depth, cls in dfs(MappedClass, graph):
            for line in dump_cls(depth, cls):
                print line


class ReindexGlobalsCommand(base.Command):
    min_args = 1
    max_args = 1
    usage = '<ini file>'
    summary = 'Reindex global objects: projects and users'
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()

        # remove global object references to
        self.log.info('Deleting global obj refs')
        GlobalObjectReference.query.remove({})

        self.log.info('Removing and then rebuilding SOLR index')
        for m in Mapper.all_mappers():
            mgr = m.collection.m
            cname = mgr.collection_name
            cls = m.mapped_class
            if cname is not None and session(cls) is solr_indexed_session:
                self.log.info('... for class %s', cls)
                g.solr.delete(q='type_s:"' + cls.type_s + '"')

                for objs in chunked_find(cls, {}):
                    refs = [GlobalObjectReference.from_object(obj)
                            for obj in objs if obj.indexable()]
                    self.log.info(
                        'Found %s "%s" objects to index' % (
                            len(refs), cls.type_s)
                    )
                    main_orm_session.flush()
                    if refs:
                        add_global_objs.post([ref._id for ref in refs])

        self.log.info('Reindex globals done')


class ReindexCommand(base.Command):
    min_args = 0
    max_args = 1
    usage = '<ini file>'
    summary = 'Reindex and re-shortlink all artifacts'
    parser = base.Command.standard_parser(verbose=True)
    parser.add_option('-p', '--project', dest='project', default=None,
                      help='project to reindex')
    parser.add_option('-n', '--neighborhood', dest='neighborhood',
                      default=None,
                      help='neighborhood to reindex (e.g. p)')

    parser.add_option('--solr', action='store_true', dest='solr',
                      help='Solr needs artifact references to already exist.')
    parser.add_option('--refs', action='store_true', dest='refs',
                      help='Update artifact references and shortlinks')

    parser.add_option('--batch', type="int", dest="batch_size", default=1000)

    def index_artifacts(self, ref_ids):
        try:
            add_artifacts(
                ref_ids,
                update_solr=self.options.solr,
                update_refs=self.options.refs
            )
        except CompoundError, err:
            self.log.exception('Error indexing artifacts:\n%r', err)
            self.log.error('%s', err.format_error())
        except Exception, e:
            self.log.exception('Error indexing artifact:\n%r', e)
        main_orm_session.flush()
        main_orm_session.clear()

    def command(self):
        self.basic_setup()
        if self.options.project:
            q_project = dict(shortname=self.options.project)
        elif self.options.neighborhood:
            neighborhood_id = Neighborhood.by_prefix(
                self.options.neighborhood)._id
            q_project = dict(neighborhood_id=neighborhood_id)
        else:
            q_project = {}

        # if none specified, do all
        if not self.options.solr and not self.options.refs:
            self.options.solr = self.options.refs = True

        for projects in chunked_find(Project, q_project):
            for p in projects:
                ref_ids = []
                c.project = p
                self.log.info('Reindex project %s', p.shortname)
                # Clear index for this project
                if self.options.solr:
                    g.solr.delete(q='project_id_s:%s' % p._id)
                if self.options.refs:
                    ArtifactReference.query.remove({
                        'artifact_reference.project_id': p._id
                    })
                    Shortlink.query.remove({'project_id': p._id})

                app_config_ids = []
                for ac in p.app_configs:
                    app_config_ids.append(ac._id)

                # Traverse the inheritance graph, finding all artifacts that
                # belong to this project

                for a_cls in iter_artifact_classes():
                    self.log.info('  %s', a_cls)

                    # Create artifact references and shortlinks
                    try:
                        artifacts = a_cls.query.find(dict(
                            app_config_id={'$in': app_config_ids}))
                    except Exception:
                        msg = "Unable to query artifacts of class '{}'."
                        self.log.exception(msg.format(a_cls.__name__))
                        artifacts = None
                    while True:
                        try:
                            a = next(artifacts)
                            if self.options.verbose:
                                self.log.info('      %s', a.shorthand_id())
                            if self.options.refs:
                                try:
                                    ArtifactReference.from_artifact(a)
                                    Shortlink.from_artifact(a)
                                except Exception:
                                    self.log.exception(
                                        'Making Index Objs from %s', a)
                                    continue
                            ref_ids.append(a.index_id())
                            self.log.info('adding %s for indexing',
                                          a.index_id())
                        except StopIteration:
                            break
                        except Exception:
                            msg = ("Unanticipated exception indexing artifact "
                                   "of class '{}'.")
                            self.log.exception(msg.format(a_cls.__name__))

                    # prevent nasty session buildup
                    main_orm_session.flush()
                    session(a_cls).clear()
                    main_orm_session.flush()
                    main_orm_session.clear()
                    session(a_cls).clear()

                for refs in izip_longest(*[iter(ref_ids)] * 1024):
                    indexes = filter(None, refs)
                    if indexes:
                        self.index_artifacts(indexes)
                        main_orm_session.flush()
                        main_orm_session.clear()
                        project_orm_session.clear()
                        solr_indexed_session.clear()
        self.log.info('Reindex done')


class EnsureIndexCommand(base.Command):
    min_args = 0
    max_args = 1
    usage = '[<ini file>]'
    summary = 'Run ensure_index on all mongo objects'
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        self.collect_and_update()

    def collect_and_update(self):
        # Collect indexes by collection name
        main_indexes = defaultdict(list)
        project_indexes = defaultdict(list)
        self.log.info('Collecting indexes...')
        main_sessions = {main_orm_session, repository_orm_session,
                         solr_indexed_session, artifact_orm_session}

        for m in Mapper.all_mappers():
            mgr = m.collection.m
            cname = mgr.collection_name
            cls = m.mapped_class
            if cname is None:
                self.log.info('... skipping abstract class %s', cls)
                continue
            self.log.info('... for class %s', cls)
            if session(cls) in main_sessions:
                idx = main_indexes[cname]
            else:
                idx = project_indexes[cname]
            idx.extend(mgr.indexes)
        self.log.info('Updating indexes for main DB')
        db = main_doc_session.db
        for name, indexes in main_indexes.iteritems():
            self._update_indexes(db[name], indexes)
        self.log.info('Updating indexes for project DBs')
        projects = Project.query.find().all()
        configured_dbs = set()
        for p in projects:
            db = p.database_uri
            if db in configured_dbs:
                continue
            configured_dbs.add(db)
            c.project = p
            db = project_doc_session.db
            self.log.info('... DB: %s', db)
            for name, indexes in project_indexes.iteritems():
                self._update_indexes(db[name], indexes)

    def _update_indexes(self, collection, indexes):
        prev_indexes = {}
        prev_uindexes = {}
        uindexes, rindexes = {}, {}
        for i in indexes:
            if i.unique:
                uindexes[tuple(i.index_spec)] = i
            else:
                rindexes[tuple(i.index_spec)] = i
        for iname, fields in collection.index_information().iteritems():
            if iname == '_id_':
                continue
            if fields.get('unique'):
                prev_uindexes[iname] = tuple(fields['key'])
            else:
                prev_indexes[iname] = tuple(fields['key'])
                # Drop obsolete indexes
        for iname, key in prev_indexes.iteritems():
            if key not in rindexes:
                self.log.info('...... drop index %s:%s', collection.name,
                              iname)
                collection.drop_index(iname)
        for iname, key in prev_uindexes.iteritems():
            if key not in uindexes:
                self.log.info('...... drop index %s:%s', collection.name,
                              iname)
                collection.drop_index(iname)
                # Ensure all indexes
        for name, idx in uindexes.iteritems():
            self.log.info('...... ensure %s:%s', collection.name, idx)
            while True:
                try:
                    collection.ensure_index(idx.index_spec, unique=True)
                    break
                except DuplicateKeyError, err:
                    self.log.info('Found dupe key(%s), eliminating dupes', err)
                    self._remove_dupes(collection, idx.index_spec)
        for name, idx in rindexes.iteritems():
            self.log.info('...... ensure %s:%s', collection.name, idx)
            collection.ensure_index(idx.index_spec, background=True)

    def _remove_dupes(self, collection, spec):
        iname = collection.create_index(spec)
        fields = [f[0] for f in spec]
        q = collection.find({}, fields=fields).sort(spec)

        def keyfunc(doc):
            return tuple(doc.get(f, None) for f in fields)

        dupes = []
        for key, doc_iter in groupby(q, key=keyfunc):
            docs = list(doc_iter)
            if len(docs) > 1:
                self.log.info('Found dupes with %s', key)
                dupes += [doc['_id'] for doc in docs[1:]]
        collection.drop_index(iname)
        collection.remove(dict(_id={'$in': dupes}))


def build_model_inheritance_graph():
    graph = dict((m.mapped_class, ([], [])) for m in Mapper.all_mappers())
    for cls, (parents, children) in graph.iteritems():
        for b in cls.__bases__:
            if b not in graph:
                continue
            parents.append(b)
            graph[b][1].append(cls)
    return graph


def dump_cls(depth, cls):
    indent = ' ' * 4 * depth
    yield indent + '%s.%s' % (cls.__module__, cls.__name__)
    m = mapper(cls)
    for p in m.properties:
        s = indent * 2 + ' - ' + str(p)
        if hasattr(p, 'field_type'):
            s += ' (%s)' % p.field_type
        yield s


def dfs(root, graph, depth=0):
    yield depth, root
    for c in graph[root][1]:
        for r in dfs(c, graph, depth + 1):
            yield r


def pm(etype, value, tb):  # pragma no cover
    import pdb
    import traceback

    try:
        from IPython.ipapi import make_session

        make_session()
        from IPython.Debugger import Pdb

        sys.stderr.write('Entering post-mortem IPDB shell\n')
        p = Pdb(color_scheme='Linux')
        p.reset()
        p.setup(None, tb)
        p.print_stack_trace()
        sys.stderr.write('%s: %s\n' % (etype, value))
        p.cmdloop()
        p.forget()
        # p.interaction(None, tb)
    except ImportError:
        sys.stderr.write('Entering post-mortem PDB shell\n')
        traceback.print_exception(etype, value, tb)
        pdb.post_mortem(tb)


class ReindexNotifications(base.Command):
    min_args = 1
    max_args = 1
    usage = '<ini file>'
    summary = 'Reindex notification objects'
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()

        # remove global object references to notifications
        self.log.info('Deleting global obj refs')
        GlobalObjectReference.query.remove({
            '_id': {'$regex': '^vulcanforge/notification/model/Notification'},
        })

        self.log.info('Removing and then rebuilding notification index')

        m = Mapper.by_classname('Notification')
        mgr = m.collection.m
        cname = mgr.collection_name
        cls = m.mapped_class
        if cname is not None and session(cls) is solr_indexed_session:
            self.log.info('... for class %s', cls)
            g.solr.delete(q='type_s:"' + cls.type_s + '"')

            for objs in chunked_find(cls, {}):
                refs = [GlobalObjectReference.from_object(obj)
                        for obj in objs if obj.indexable()]
                self.log.info(
                    'Found %s "%s" objects to index' % (
                        len(refs), cls.type_s)
                )
                main_orm_session.flush()
                if refs:
                    add_global_objs.post([ref._id for ref in refs])

        self.log.info('Reindex notifications done')
