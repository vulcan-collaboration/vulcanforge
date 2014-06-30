.. _neighborhood:

Neighborhood
============

.. automodule:: vulcanforge.neighborhood

.. inheritance-diagram:: vulcanforge.neighborhood.model.Neighborhood

Neighborhood objects are used to group and organize :doc:`project` objects.

This organization direclty affects the URL of a given project. For instance: A
project shortnamed ``my-project`` in the neighborhood with the prefix
``my-neighborhood`` will have the URL
``http://my-platform.something/my-neighborhood/my-project``.

.. autoclass:: vulcanforge.neighborhood.model.Neighborhood
    :members:
