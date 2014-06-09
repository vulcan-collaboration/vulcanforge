Extending Vulcan
================

A Vulcan application's capabilities can be extended in several ways which allow
solutions to be custom tailored for a broad range of domains.

Custom Visualizers
------------------

Registering custom visualizers capable of rendering proprietary file formats or
adding new views beyond highlighted source text is remarkably easy with the
provided Visualizer hooks.

Basic Rendering Visualizer
^^^^^^^^^^^^^^^^^^^^^^^^^^

Basic Processing Visualizer
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Custom Tools (:doc:`Applications <application>`)
------------------------------------------------

:doc:`Applications <application>` can be seen as tools available to teams
(:doc:`Projects <project>`) and are sometimes referred to as Tools for
disambiguation. Adding specific functionality to users within the scope of
their project is done by adding new Tools to the platform. The Tool system is
designed to be extended easily.

Adding a new Tool is done by defining your Tool as a subclass of
:py:class:`~vulcanforge.common.app.application.Application` and registering it
as a tool with your Vulcan deployment's
:py:class:`~vulcanforge.config.ToolManager` class.
