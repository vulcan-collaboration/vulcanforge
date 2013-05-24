from contextlib import contextmanager

from bson import ObjectId
from bson.errors import InvalidId
from pylons import tmpl_context as c

from vulcanforge.common.exceptions import ForgeError, NoSuchAppError
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.neighborhood.exceptions import NoSuchNeighborhoodError
from vulcanforge.project.model import Project, AppConfig
from vulcanforge.project.exceptions import NoSuchProjectError


class ContextManager(object):

    def set(self, project_shortname=None, mount_point=None,
                    app_config_id=None, neighborhood=None):
        if not isinstance(neighborhood, Neighborhood):
            if neighborhood is not None:
                n = Neighborhood.query.get(name=neighborhood)
                if n is None:
                    try:
                        n = Neighborhood.query.get(
                            _id=ObjectId(str(neighborhood)))
                    except InvalidId:
                        pass
                if n is None:
                    raise NoSuchNeighborhoodError(
                        "Couldn't find neighborhood %s" % repr(neighborhood)
                    )
                neighborhood = n

        p = None
        if project_shortname is not None:
            query = dict(shortname=project_shortname)
            if neighborhood is not None:
                query['neighborhood_id'] = neighborhood._id
            p = Project.query.get(**query)
            if p is None:
                try:
                    del query['shortname']
                    query['_id'] = ObjectId(str(project_shortname))
                    p = Project.query.get(**query)
                except InvalidId:
                    pass

            if p is None:
                raise NoSuchProjectError("Couldn't find project %s" %
                                         repr(project_shortname))

        if app_config_id is None:
            if p is None:
                raise ForgeError("Must specify app_config_id if not project")
            c.app = p.app_instance(mount_point)
        else:
            if isinstance(app_config_id, basestring):
                app_config_id = ObjectId(app_config_id)
            app_config = AppConfig.query.get(_id=app_config_id)
            if p is None:
                if app_config is None:
                    raise NoSuchAppError('Could not find app_config {}'.format(
                        app_config_id))
                p = app_config.project
            c.app = p.app_instance(app_config)

        c.project = p

    @contextmanager
    def push(self, project_id=None, mount_point=None,
                     app_config_id=None, neighborhood=None):
        project = getattr(c, 'project', ())
        app = getattr(c, 'app', ())
        self.set(project_id, mount_point, app_config_id,
                 neighborhood=neighborhood)
        try:
            yield
        finally:
            if project == ():
                del c.project
            else:
                c.project = project
            if app == ():
                del c.app
            else:
                c.app = app