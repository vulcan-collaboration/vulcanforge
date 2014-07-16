Vulcan Concepts
===============

The Ming Object Document Mapper (ODM)
-------------------------------------

Vulcan applications use the `Ming`_ ODM which sits on `pymongo`_ to interact
with the mongodb database. Most of the persisted core object types in a Vulcan
application subclass `Ming`_ :py:class:`ming.odm.MappedClass`. The Vulcan
:doc:`middleware` handles setting up the database session.

For more details see the official `Ming Documentation`_.

.. _`Ming`: http://merciless.sourceforge.net/tour.html
.. _`Ming Documentation`: http://merciless.sourceforge.net/tour.html
.. _pymongo: http://api.mongodb.org/python/current/

Core Object Classes
-------------------

Vulcan provides framework support for organizing secured virtual teams.
:doc:`Projects <project>` are organized into :doc:`Neighborhoods <neighborhood>`

.. graphviz:: core_object_classes.dot

.. toctree::
    :maxdepth: 1

    user
    neighborhood
    project
    application
    appconfig
    artifact

Access Control
--------------

Access control is defined by the use of Access Control Lists (ACLs) and Access
Control Entries (ACEs). :doc:`Neighborhoods <neighborhood>`,
:doc:`Projects <project>`, :doc:`AppConfigs <application>`, and
:doc:`Artifacts <artifact>` each have an ACL which inherits entries from it's
parent.
