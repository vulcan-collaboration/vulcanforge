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

A simple rendering visualizer can be added via the web UI in the designated
forgeadmin project (specified in the config file.) A visualizer package is a ZIP
file containing at least an html entry point and a *manifest.json* which
declares the entry point.

When triggered the designated entry point (*i.e. - index.html*) will be loaded
with the GET query parameter *resource_url* being the URL of the file to be
visualized. The entry point html is responsible for using javascript or some
other means of retrieving the resource and displaying whatever it is designed
to display.

Basic Processing Visualizer
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Processing Visualizers further extend the flexibility of the Visualizer system
with a preprocessing step. Examples of this feature are calculating metrics out
of a large proprietary file format into an easily parseable JSON representation
or processing parametric CAD files into compact tessallated formats to be
loaded into interactive previews using WebGL.


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
:py:class:`~vulcanforge.config.ToolManager` class's `default_tools` dictionary.

