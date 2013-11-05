# -*- coding: utf-8 -*-

"""
util

@author: U{tannern<tannern@gmail.com>}
"""


class MappedClassFieldReference(object):

    def __init__(self, model, attribute, key=None):
        self.model = model
        self.attribute = attribute
        self.key = key

    def __str__(self):
        s = '{}.{}'.format(self.model.__name__, self.attribute)
        if self.key is not None:
            s += '["{}"]'.format(self.key)
        return s

    def iter_instances(self):
        return self.model.query.find()

    def get_value(self, instance):
        value = getattr(instance, self.attribute)
        if self.key is not None:
            value = value.get(self.key)
        return value

    def set_value(self, instance, value):
        query = {'_id': instance._id}
        field_key = self.attribute
        if self.key is not None:
            field_key += '{}'.format(self.key)
        update = {
            '$set': {
                field_key: value
            }
        }
        self.model.query.update(query, update)
