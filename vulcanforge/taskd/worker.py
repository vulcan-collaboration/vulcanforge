import os
import sys
import time
import logging
from ming.odm import ThreadLocalODMSession

from webob import Request
from paste.deploy import loadapp
from paste.deploy.converters import asint
import pylons
from tg import config
from vulcanforge.taskd import MonQTask

from vulcanforge.taskd.exceptions import QueueConnectionError, TaskdException


class TaskdWorker(object):

    def __init__(self, config_path, name='worker', only=None,
                 relative_path=None, log=None):
        self.config_path = config_path
        if relative_path is None:
            relative_path = os.getcwd()
        self.relative_path = relative_path
        self.name = name
        self.only = only
        self.keep_running = True
        self.restart_when_done = False
        if log is None:
            log = logging.getLogger(__name__)
        self.log = log
        self.wsgi_app = None
        self.wsgi_error_log = None
        self.poll_interval = asint(config.get('monq.poll_interval', 10))
        self.task_queue_timeout = asint(config.get('task_queue.timeout', 2))

    def graceful_restart(self, signum, frame):
        self.log.info('taskd pid %s recieved signal %s restarting gracefully',
                      os.getpid(), signum)
        self.restart_when_done = True
        self.keep_running = False

    def graceful_stop(self, signum, frame):
        self.log.info('taskd pid %s recieved signal %s stopping gracefully',
                      os.getpid(), signum)
        self.keep_running = False

    def log_current_task(self, signum, frame):
        self.log.info('taskd pid %s is currently handling task %s',
                      os.getpid(), getattr(self, 'task', None))

    def start_app(self):
        self.wsgi_app = loadapp(
            'config:%s#task' % self.config_path,
            relative_to=self.relative_path)

        # this is only present to avoid errors within weberror's
        # ErrorMiddleware if the default error stream (stderr?) doesn't work
        wsgi_error_log_path = pylons.config.get('taskd.wsgi_log', '/dev/null')
        self.wsgi_error_log = open(wsgi_error_log_path, 'a')

    def run_task(self, task):

        def start_response(status, headers, exc_info=None):
            pass

        # Build the (fake) request
        try:
            self.log.debug(task.task_name)
            r = Request.blank('/--%s--/' % task.task_name, {
                'task': task,
                'wsgi.errors': self.wsgi_error_log or self.log,
            })
            result = list(self.wsgi_app(r.environ, start_response))
        except TaskdException, e:
            # task failed to complete
            self.log.error(
                'taskd worker failed; %s; %s -- %s',
                e.message, task.task_name, task._id)
        except Exception:
            # unknown exception
            self.log.exception('taskd worker error')
        finally:
            self.wsgi_error_log.flush()

    def _waitfunc_queue(self):
        while self.keep_running:
            taskid = pylons.app_globals.task_queue.get(
                timeout=self.task_queue_timeout)
            if taskid:
                self.log.debug('got item %s from redis queue', taskid)
                return

    def _waitfunc_noq(self):
        time.sleep(self.poll_interval)

    def event_loop(self):
        self.start_app()

        only = self.only
        if only:
            only = only.split(',')

        if pylons.app_globals.task_queue:
            waitfunc = self._waitfunc_queue
        else:
            waitfunc = self._waitfunc_noq

        # run any available tasks on startup
        for task in MonQTask.event_loop(process=self.name, only=only):
            if task:
                self.run_task(task)
            else:
                break

        # enter the loop
        eloop = MonQTask.event_loop(waitfunc, process=self.name, only=only)
        while self.keep_running:
            try:
                self.task = next(eloop)
            except QueueConnectionError:
                self.log.exception("taskd cannot connect to task_queue")
                eloop = MonQTask.event_loop(
                    self._waitfunc_noq, process=self.name, only=only)
                self.task = None
            if self.task:
                self.run_task(self.task)

        self.log.info('taskd pid %s stopping gracefully.', os.getpid())

        if self.restart_when_done:
            self.log.info('taskd pid %s restarting itself.', os.getpid())
            os.execv(sys.argv[0], sys.argv)
