AppConfig (installed Tool)
==========================

Custom :py:class:`~vulcanforge.common.app.application.Application` subclasses
define a tool's behavior while :py:class:`~vulcanforge.project.model.AppConfig`
instances represent an installed
:py:class:`~vulcanforge.common.app.application.Application` within a
:py:class:`~vulcanforge.project.model.Project`.

:py:class:`~vulcanforge.artifact.model.Artifact` instances keep a reference to
their parent :py:class:`~vulcanforge.project.model.AppConfig` which keep a
reference to their parent :py:class:`~vulcanforge.project.model.Project`.

.. autoclass:: vulcanforge.project.model.AppConfig
    :members:
