import logging
from bson import ObjectId
import itertools

from formencode.validators import StringBool, UnicodeString
from pylons import app_globals as g, tmpl_context as c
from tg.decorators import expose, validate, with_trailing_slash

from vulcanforge.common.controllers import BaseController
from vulcanforge.common.helpers import slugify
from vulcanforge.project.model import Project

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:search/templates/'


class AutocompleteController(BaseController):
    """
    Exposes JSON views for use in autocomplete widgets.

    """
    DEFAULT_LIMIT = 10

    def __init__(self, solr=None):
        if solr is not None:
            self.solr = solr
        else:
            self.solr = g.solr

    def _check_security(self):
        g.security.require_authenticated()

    def _solr_query(self, type_s, query, fq=None, limit=DEFAULT_LIMIT,
                    id_field='id', value_field=None, label_field=None):
        """
        Query SOLR.

        :param type_s: The type to filter for.
        :type  type_s: str
        :param query: The string to query for
        :type  query: str
        :param limit: The maximum number of results to return
        :type  limit: int
        :return: The SOLR results

        """
        if not query:
            return []
        queries = ['({0}* OR {0}~)'.format(query.strip())]
        if value_field is not None:
            queries.append('{0}:{1}'.format(value_field, queries[0]))
        if label_field is not None:
            try:
                label = label_field['solr_field']
            except TypeError:
                label = label_field
            queries.append('{0}:{1}'.format(label, queries[0]))
        if fq is not None:
            fq = [fq]
        else:
            fq = []
        fq.append('type_s:"{}"'.format(type_s))
        fq.append('read_roles:({})'.format(
            ' OR '.join(g.security.get_user_read_roles())
        ))
        params = {
            'q': ' OR '.join(queries),
            'fq': fq,
            'rows': limit,
            }
        solr_result = self.solr.search(**params)

        def extract_field(entry, field):
            try:
                display_field = field['display_field']
            except TypeError:
                display_field = field
            if callable(display_field):
                return display_field(entry)
            elif display_field in entry:
                return entry[display_field]

        def extract_fields(entry):
            return {
                'id': extract_field(entry, id_field),
                'value': extract_field(entry, value_field),
                'label': extract_field(entry, label_field),
                }

        output = [extract_fields(entry) for entry in solr_result.docs]
        return output

    @expose()
    def index(self, **kw):
        return None

    @expose('json')
    def user(self, q, limit=DEFAULT_LIMIT, **kw):
        def get_label(entry):
            return "{display_name_s} ({username_s})".format(**entry)
        return {
            'results': self._solr_query(
                'User', q, limit=limit, id_field="id",
                value_field="username_s",
                label_field={
                    'solr_field': "display_name_s",
                    'display_field': get_label,
                }
            ),
        }

    @expose('json')
    def project(self, q, limit=DEFAULT_LIMIT, **kw):
        return {
            'results': self._solr_query(
                'Project', q, limit=limit, id_field="id",
                value_field="shortname_s", label_field="name_s")
        }

    @expose('json')
    def project_labels(self, project_id, q, limit=DEFAULT_LIMIT, **kw):
        project = Project.query.get(_id=ObjectId(project_id))
        labels = []
        for label, count in project.get_label_counts().items():
            if q not in label:
                continue
            labels.append({
                'id': label,
                'label': '{} ({})'.format(label, count),
                'value': label,
                'count': count,
                })
        return {
            'labels': sorted(labels, key=lambda x: x['count']),
            }


class SearchController(BaseController):

    def _get_excluded_types(self):
        return (
            "Generic Artifact",
            "Bin",
            "Discussion",
            "Post",
            "Post Snapshot",
            "WikiPage Snapshot",
            )

    def _x_searchable_types(self, q):
        params = {
            "q": q,
            "facet": "on",
            "facet.field": "type_s",
            "rows": 0
        }
        result = g.search(**params)
        # iterate in chunks of 2 (type_s, count)
        if result is not None:
            for type_s, count in itertools.izip(
                *[iter(result.facets['facet_fields']['type_s'])] * 2):
                if count and type_s not in self._get_excluded_types():
                    yield {
                        "name": type_s,
                        "count": count
                    }

    def _get_searchable_type_dicts(self, q):
        return [{
                    "name": type['name'],
                    "enabled": True,
                    "count": type['count'],
                    "fieldname": "filter.%s" % slugify(type['name']),
                    }
                for type in sorted(self._x_searchable_types(q),
            key=lambda t: t['name'])]

    def _get_complete_query(self, q, history=False):
        return q + ' AND %s' % (
            ' AND '.join((
                'NOT type_s:("%s")' % '" OR "'.join(
                    self._get_excluded_types()),
                'read_roles:("%s")' % '" OR "'.join(
                    g.security.get_user_read_roles()),
                'NOT withdrawn_b:true',
                'is_history_b:%s' % history
                ))
            )

    @expose(TEMPLATE_DIR + 'index.html')
    @validate(dict(
        q=UnicodeString(),
        history=StringBool(if_empty=False)
    ))
    @with_trailing_slash
    def index(self, q='', history=False, limit=25, page=0, **kw):
        if q:
            types = self._get_searchable_type_dicts(
                self._get_complete_query(q, history)
            )
        else:
            types = []
        search_uri = '/search/search'
        c.search_query = q
        return dict(q=q, search_uri=search_uri, limit=limit,
            page=page, types=types, bodyClasses=['global-search'])

    @validate(dict(
        q=UnicodeString(),
        history=StringBool(if_empty=False)
    ))
    @expose('json')
    def search(self, q=u'', startPos=0, mode='simple', page=None, limit=25,
               history=False, **kw):
        if q:
            complete_q = self._get_complete_query(q, history)
            types = self._get_searchable_type_dicts(complete_q)
            params = {
                "q": complete_q,
                "start": startPos,
                "rows": limit,
                "fl": '*,score'
            }
            if mode == 'advanced':
                for type in types:
                    type['enabled'] = type['enabled'] and\
                                      type['fieldname'] in kw
                params['fq'] = 'type_s:("%s")' % (
                    '" OR "'.join([type['name']
                                   for type in types if type['enabled']])
                    )
            results = g.search(**params)
            if results:
                count = results.hits
                results_list = []
                max_params = params.copy()
                max_params.update({
                    'rows': 1,
                    'start': 0,
                    'fl': 'score'
                })
                max_score = g.search(**max_params).docs[0]['score']
                for doc in results.docs:
                    doc['rel_score'] = 10. * doc['score'] / max_score
                    results_list.append(doc)
            else:
                results_list = []
                count = 0
        else:
            results_list = []
            count = 0
        return dict(q=q, results=results_list,
            count=count, page=page, limit=limit)

    @expose()
    def help(self):
        return dict()
