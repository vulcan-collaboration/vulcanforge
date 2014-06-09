Vulcan Concepts
===============

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
    artifact

Access Control
--------------

Access control is defined by the use of Access Control Lists (ACLs) and Access
Control Entries (ACEs). :doc:`Neighborhoods <neighborhood>`,
:doc:`Projects <project>`, :doc:`AppConfigs <application>`, and
:doc:`Artifacts <artifact>` each have an ACL which inherits entries from it's
parent.
