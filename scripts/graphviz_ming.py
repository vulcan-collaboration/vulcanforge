# -*- coding: utf-8 -*-

"""
graphviz_ming

@author: U{tannern<tannern@gmail.com>}
"""
import sys
import argparse
from datetime import datetime
import ming.schema
from ming.odm import Mapper, ForeignIdProperty, RelationProperty


SCHEMA_LABELS = {
    int: 'int',
    str: 'str',
    datetime: 'datetime',
    bool: 'bool'
}


def is_hashable(x):
    try:
        hash(x)
    except TypeError:
        return False
    else:
        return True


def get_all_mappers():
    return Mapper.all_mappers()


def get_class_key(cls):
    return '"{}.{}"'.format(cls.__module__, cls.__name__)


def get_document_key(document):
    cls = document.__class__
    return '"{}.{}.{}"'.format(cls.__module__, cls.__name__, document._id)


def get_label_for_schema_item(schema_item):
    if isinstance(schema_item, type):
        if issubclass(schema_item, ming.schema.SchemaItem):
            schema_item = schema_item()
        elif is_hashable(schema_item) and schema_item in SCHEMA_LABELS:
            return SCHEMA_LABELS[schema_item]
    if not isinstance(schema_item, ming.schema.FancySchemaItem):
        schema_item = ming.schema.SchemaItem.make(schema_item)
    if isinstance(schema_item, ming.schema.Object):
        field_schemas = ['{}: {}'.format(get_label_for_schema_item(k),
                                         get_label_for_schema_item(f))
                         for k, f in schema_item.field_items]
        return r'\{' + ', '.join(field_schemas) + r'\}'
    elif isinstance(schema_item, ming.schema.Array):
        item_label = get_label_for_schema_item(schema_item.field_type)
        return '[{}]'.format(item_label)
    elif isinstance(schema_item, ming.schema.Value):
        return schema_item.value
    elif isinstance(schema_item, ming.schema.OneOf):
        return 'OneOf:[{}]'.format(', '.join(schema_item.options))
    elif isinstance(schema_item, ming.schema.SchemaItem):
        return schema_item.__class__.__name__
    elif isinstance(schema_item, basestring):
        return schema_item
    else:
        raise Exception("{}: {}".format(schema_item.__class__, schema_item))
        return str(schema_item)


class DotGraph(object):
    root_template = 'digraph'
    edge_template = '->'

    def __init__(self, name="G", options=None, node_options=None,
                 edge_options=None):
        self.name = name
        self.options = options or {}
        self.node_options = node_options or {}
        self.edge_options = edge_options or {}
        self.nodes = {}
        self.edges = []
        self.subgraphs = {}

    def add_node(self, name, **options):
        if name not in self.nodes:
            self.nodes[name] = options

    def add_edge(self, a, b, **options):
        self.edges.append([a, b, options])

    def write_to_stream(self, stream):
        # open
        stream.write("{} {} {{\n".format(self.root_template, self.name))
        if self.options:
            for key, value in self.options.items():
                stream.write('{}={};\n'.format(key, value))
        if self.node_options:
            option_strings = ['{}="{}"'.format(key, value)
                              for key, value in self.node_options.items()]
            stream.write('node [')
            stream.write(', '.join(option_strings))
            stream.write('];\n')
        if self.edge_options:
            option_strings = ['{}="{}"'.format(key, value)
                              for key, value in self.edge_options.items()]
            stream.write('edge [')
            stream.write(', '.join(option_strings))
            stream.write('];\n')

        # nodes
        for node_key, options in self.nodes.items():
            stream.write('{}'.format(node_key))
            if options:
                option_strings = ['{}="{}"'.format(key, value)
                                  for key, value in options.items()]
                stream.write(' [')
                stream.write(', '.join(option_strings))
                stream.write(']')
            stream.write(';\n')

        # edges
        for a, b, options in self.edges:
            stream.write('{} {} {}'.format(a, self.edge_template, b))
            if options:
                option_strings = ['{}="{}"'.format(key, value)
                                  for key, value in options.items()]
                stream.write(' [')
                stream.write(', '.join(option_strings))
                stream.write(']')
            stream.write(';\n')

        # close
        stream.write("}\n")


class MapperDotGraph(DotGraph):
    def __init__(self, recursive=True, *args, **kwargs):
        super(MapperDotGraph, self).__init__(*args, **kwargs)
        self._recursive = recursive


class InheritanceDotGraph(MapperDotGraph):
    root_template = 'digraph'
    edge_template = '->'

    def add_mapper(self, mapper):
        mapped_class = mapper.mapped_class
        cls_key = get_class_key(mapped_class)
        label_fields = [mapped_class.__name__]
        for mapper_property in mapper.properties:
            if not hasattr(mapper_property, 'field'):
                continue
            label_fields.append('<{0}> {0}: {1}'.format(
                mapper_property.name,
                get_label_for_schema_item(mapper_property.field.type)))
        node_options = {
            'label': '{ '+' | '.join(label_fields)+' }',
            'shape': 'record'
        }
        self.add_node(cls_key, **node_options)
        for base_class in mapped_class.__bases__:
            base_key = get_class_key(base_class)
            self.add_node(base_key, label=base_class.__name__)
            self.add_edge(base_key, cls_key)


class RelationsDotGraph(MapperDotGraph):
    root_template = 'graph'
    edge_template = '--'

    def add_mapper(self, mapper):
        mapped_class = mapper.mapped_class
        cls_key = get_class_key(mapped_class)
        label_fields = [mapped_class.__name__]
        for mapper_property in mapper.properties:
            if not isinstance(mapper_property, ForeignIdProperty):
                continue
            label_fields.append('<{0}> {0}'.format(mapper_property.name))
            related_class = mapper_property.related
            related_key = get_class_key(related_class)
            self.add_edge(cls_key+':'+mapper_property.name, related_key,
                          color="blue")
        node_options = {
            'label': '{ '+' | '.join(label_fields)+' }',
            'shape': 'record'
        }
        self.add_node(cls_key, **node_options)


class DocumentsDotGraph(MapperDotGraph):
    root_template = 'graph'
    edge_template = '--'

    def add_mapper(self, mapper):
        mapped_class = mapper.mapped_class
        try:
            document_cursor = mapped_class.query.find()
        except:
            pass
        else:
            map(self.add_document, document_cursor)

    def add_document(self, document):
        document_key = get_document_key(document)
        label_fields = [document_key.strip('"')]
        if hasattr(document, 'name') and document.name:
            label_fields.append('<name> name: ' + document.name)
        for mapper_property in document.__ming__.mapper.properties:
            if not isinstance(mapper_property, ForeignIdProperty):
                continue
            related_class = mapper_property.related
            related_id = getattr(document, mapper_property.name)
            label_fields.append('<{0}> {0}: {1}'.format(mapper_property.name,
                                                        related_id))
            if related_id is None:
                continue
            related_key = '"{}.{}.{}"'.format(related_class.__module__,
                                              related_class.__name__,
                                              related_id)
            self.add_edge(document_key+':'+mapper_property.name, related_key,
                          color="blue")
        node_options = {
            'label': '{ '+' | '.join(label_fields)+' }',
            'shape': 'record'
        }
        self.add_node(document_key, **node_options)


def graph_inheritance(args):
    graph = InheritanceDotGraph()
    map(graph.add_mapper, get_all_mappers())
    graph.write_to_stream(sys.stdout)


def graph_relations(args):
    options = {
        'layout': 'neato',
        'overlap': 'false'
    }
    graph = RelationsDotGraph(options=options)
    map(graph.add_mapper, get_all_mappers())
    graph.write_to_stream(sys.stdout)


def graph_documents(args):
    options = {
        'layout': 'neato',
        'overlap': 'false'
    }
    graph = DocumentsDotGraph(options=options)
    if args.classes:
        for class_name in args.classes:
            graph.add_mapper(Mapper.by_classname(class_name))
    else:
        map(graph.add_mapper, get_all_mappers())
    graph.write_to_stream(sys.stdout)


if __name__ == '__main__':
    mapped_classes = [m.mapped_class.__name__ for m in Mapper.all_mappers()]

    parser = argparse.ArgumentParser(description="Make Graphz!!1!")
    subparsers = parser.add_subparsers()

    parser_documents = subparsers.add_parser('inheritance')
    parser_documents.set_defaults(func=graph_inheritance)

    parser_documents = subparsers.add_parser('relations')
    parser_documents.set_defaults(func=graph_relations)

    parser_documents = subparsers.add_parser('documents')
    parser_documents.add_argument('classes', nargs='*')
    parser_documents.set_defaults(func=graph_documents)

    args = parser.parse_args()
    args.func(args)

    sys.exit()
