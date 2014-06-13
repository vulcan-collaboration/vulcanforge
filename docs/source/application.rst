Applications (a.k.a. Tools)
===========================

:py:class:`Users <vulcanforge.auth.model.User>` are members of
:py:class:`Projects <vulcanforge.project.model.Project>` which are containers
for :py:class:`Applications <vulcanforge.common.app.application.Application>`,
commonly referred to as *Tools* here for disambiguation, which can be containers
for :py:class:`Artifacts <vulcanforge.artifact.model.Artifact>`.

Vulcan includes several already made tools (Wiki, Tracker, Downloads,
Discussions, etc...) along with some functionally required tools (home,
neighborhood_home)

A tool is defined in a subclass of
:py:class:`vulcanforge.common.app.application.Application` and registered with
the :py:class:`~vulcanforge.config.ToolManager` class's `default_tools`
dictionary.

.. automodule:: vulcanforge.common.app

.. automodule:: vulcanforge.common.app.application

.. inheritance-diagram:: vulcanforge.common.app.application.Application

.. autoclass:: vulcanforge.common.app.application.Application
    :show-inheritance:
    :members:
