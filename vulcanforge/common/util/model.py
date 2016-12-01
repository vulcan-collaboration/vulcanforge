import logging

import bson
from ming import schema
from ming.odm import (
    state,
    mapper,
    Mapper,
    ThreadLocalODMSession,
    RelationProperty
)
from ming.odm.declarative import MappedClass
from ming.odm.icollection import InstrumentedList
from ming.utils import LazyProperty

LOG = logging.getLogger(__name__)


class VFRelationProperty(RelationProperty):
    """Relation property that sets itself on set, to the issue where relation
    properties that are set will set the associated foreign key property but
    not itself, e.g.:

    # nbhd is not yet flushed to the db in this case
    >>> project.neighborhood = nbhd
    >>> print project.neighborhood
    None

    Also prevents a query to the database when the related property is flushed.

    """
    def __set__(self, instance, value):
        super(VFRelationProperty, self).__set__(instance, value)
        if self.fetch:
            st = state(instance)
            st.extra_state[self] = value


def chunked_find(cls, query=None, pagesize=1024):
    if query is None:
        query = {}
    page = 0
    while True:
        results = (
            cls.query.find(query)
            .skip(pagesize * page)
            .limit(pagesize)
            .all())
        if not results:
            break
        yield results
        page += 1


def build_model_inheritance_graph():
    graph = dict((m.mapped_class, ([], [])) for m in Mapper.all_mappers())
    for cls, (parents, children) in graph.iteritems():
        for b in cls.__bases__:
            if b not in graph:
                continue
            parents.append(b)
            graph[b][1].append(cls)
    return graph


def dfs(root, graph, depth=0):
    yield depth, root
    for c in graph[root][1]:
        for r in dfs(c, graph, depth + 1):
            yield r


def pymongo_db_collection(mapped_class):
    from ming.odm import session
    db = session(mapped_class).impl.bind.db
    return db, db[mapped_class.__mongometa__.name]


def close_all_mongo_connections():
    """
    Close all pymongo connections.

    This is necessary for ReplicaSetConnection objects, because they start
    some freaky background task.
    """
    for sess in ThreadLocalODMSession._session_registry.values():
        if sess.impl.bind:
            sess.impl.bind.conn.close()


def dict_mingobject(obj, resolve=[], exclude_properties=[],
                    class_properties=None):
    result = {}

    if obj is None:
        return result

    if class_properties is None:
        class_properties = {}

    if obj.__class__ in class_properties:
        property_names = class_properties[obj.__class__]
    else:
        property_names = []
        mapped_properties = mapper(obj).properties

        for prop in mapped_properties:
            if hasattr(prop, 'field') and \
               isinstance(prop.field.schema, schema.Deprecated):
                continue
            if prop.name not in exclude_properties:
                property_names.append(prop.name)

        # adding properties decorated as @property
        for property_name,value in obj.__class__.__dict__.items():
            if type(value) in [property,LazyProperty] and property_name not in exclude_properties:
                property_names.append(property_name)

        class_properties[obj.__class__] = property_names

    for property_name in property_names:
        try:
            attribute = getattr(obj, property_name)
        except Exception, e:
            LOG.warn("dict_mingobject could not resolve '%s' on <%s>",
                     property_name, obj.__class__.__name__, exc_info=e)
            continue

        if isinstance(attribute, bson.ObjectId):
            attribute = str(attribute)
        elif isinstance(attribute, MappedClass):

            if property_name in resolve:
                attribute = dict_mingobject(attribute, resolve, exclude_properties, class_properties)
            else:
                continue
        elif isinstance(attribute, (InstrumentedList, list, tuple,)):
            if len(attribute) > 0:
                element = attribute[0]
                if isinstance(element, MappedClass):
                    if property_name in resolve:
                        attribute = dict_mingobjects(attribute, resolve, exclude_properties, class_properties)
                    else:
                        attribute = []
                elif isinstance(element, bson.ObjectId):
                    attribute = dict_mingobjects(
                        attribute,
                        resolve,
                        exclude_properties,
                        class_properties)

            else:
                attribute = []
        elif attribute == float('Infinity'):
            attribute = 'Infinity'
        elif attribute == float('-Infinity'):
            attribute = '-Infinity'
        elif attribute == float('NaN'):
            attribute = 'NaN'

        result[property_name] = attribute

    return result


def dict_mingobjects(objs, resolve=[], exclude_properties=[],
                     class_properties=None):
    result = []

    if class_properties is None:
        class_properties = {}

    for obj in objs:
        if isinstance(obj, MappedClass):
            result.append(
                dict_mingobject(
                    obj, resolve, exclude_properties, class_properties)
            )
        elif isinstance(obj, bson.ObjectId):
            result.append(str(obj))
        else:
            result.append(obj)
    return result
