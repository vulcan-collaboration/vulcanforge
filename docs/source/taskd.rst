Taskd (Task Daemon)
===================

Task (or Task Daemon) is the asynchronous processing service that listens for
queued tasks and executes them. Typically one Taskd process is started for each
processing core available on the host machine.

This is a horizontally scalable service.

.. automodule:: vulcanforge.taskd

.. autofunction:: vulcanforge.taskd.task

.. autofunction:: vulcanforge.taskd.model_task
