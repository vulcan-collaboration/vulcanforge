import sys
import time
import traceback
import logging
from datetime import datetime
from bson import son

import pymongo
from pylons import tmpl_context as c, app_globals as g

import ming
from ming.utils import LazyProperty
from ming import schema as S
from ming.odm import session, FieldProperty, state, Mapper
from ming.odm.declarative import MappedClass

from vulcanforge.common.exceptions import ForgeError
from vulcanforge.common.model.session import main_orm_session

LOG = logging.getLogger(__name__)


class MonQTask(MappedClass):
    """Task to be executed by the taskd daemon.

    Properties

        - _id - bson.ObjectId() for this task
        - state - 'ready', 'busy', 'error', or 'complete' task status
        - priority - integer priority, higher is more priority
        - result_type - either 'keep' or 'forget', what to do with the task
        when
          it's done
        - time_queue - time the task was queued
        - time_start - time taskd began working on the task
        - time_stop - time taskd stopped working on the task
        - task_name - full dotted name of the task function to run
        - process - identifier for which taskd process is working on the task
        - context - values used to set c.project, c.app, c.user for the task
        - args - *args to be sent to the task function
        - kwargs - **kwargs to be sent to the task function
        - result - if the task is complete, the return value. If in error,
        the traceback.

    """
    states = ('ready', 'busy', 'error', 'complete')
    result_types = ('keep', 'forget')

    class __mongometa__:
        session = main_orm_session
        name = 'monq_task'
        indexes = [
            [
                ('state', ming.ASCENDING),
                ('priority', ming.DESCENDING),
                ('time_queue', ming.ASCENDING)
            ], [
                'state',
                'time_queue'
            ],
        ]

    _id = FieldProperty(S.ObjectId)
    state = FieldProperty(S.OneOf(*states))
    priority = FieldProperty(int)
    result_type = FieldProperty(S.OneOf(*result_types))
    time_queue = FieldProperty(datetime, if_missing=datetime.utcnow)
    time_start = FieldProperty(datetime, if_missing=None)
    time_stop = FieldProperty(datetime, if_missing=None)

    task_name = FieldProperty(str)
    process = FieldProperty(str)
    context = FieldProperty({
        'project_id': S.ObjectId,
        'app_config_id': S.ObjectId,
        'user_id': S.ObjectId
    })
    args = FieldProperty([])
    kwargs = FieldProperty({None: None})
    result = FieldProperty(None, if_missing=None)

    def __repr__(self):
        project_url = getattr(c, 'project', None) and c.project.url() or None
        app_mount = getattr(c, 'app', None) and \
                    c.app.config.options.mount_point or None
        username = getattr(c, 'user', None) and c.user.username or None
        return '<%s %s (%s) P:%d %s %s project:%s app:%s user:%s>' % (
            self.__class__.__name__,
            self._id,
            self.state,
            self.priority,
            self.task_name,
            self.process,
            project_url,
            app_mount,
            username)

    @LazyProperty
    def function(self):
        """The function that is called by this task"""
        smod, sfunc = self.task_name.rsplit('.', 1)
        cur = __import__(smod, fromlist=[sfunc])
        return getattr(cur, sfunc)

    @classmethod
    def post(cls, function, args=None, kwargs=None):
        """
        Create a new task object based on the current context.

        @type function: function
        @type args: None, list, tuple
        @type kwargs: None, dict

        @rtype: C{MonQTask}
        """
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}

        result_type = kwargs.pop('taskd_result_type', 'forget')
        priority = kwargs.pop('taskd_priority', 10)
        state = kwargs.pop('taskd_state', 'ready')

        task_name = '%s.%s' % (
            function.__module__,
            function.__name__)
        context = dict(
            project_id=None,
            app_config_id=None,
            user_id=None)
        if getattr(c, 'project', None):
            context['project_id'] = c.project._id
        if getattr(c, 'app', None):
            context['app_config_id'] = c.app.config._id
        elif getattr(c, 'app_config', None):
            context['app_config_id'] = c.app_config._id
        if getattr(c, 'user', None):
            context['user_id'] = c.user._id
        obj = cls.post_task(
            state=state,
            priority=priority,
            result_type=result_type,
            task_name=task_name,
            args=args,
            kwargs=kwargs,
            process=None,
            result=None,
            context=context
        )
        if obj:
            try:
                LOG.debug('putting %s in the task queue', obj._id)
                g.task_queue.put(str(obj._id))
            except Exception:
                LOG.exception('Error putting to task queue')
        return obj

    @classmethod
    def post_task(cls, **kw):
        obj = cls(**kw)
        session(obj).flush(obj)
        return obj

    @classmethod
    def get(cls, process='worker', state='ready', only=None):
        """Get the highest-priority, oldest, ready task and lock it to the
        current process.  If no task is available and waitfunc is supplied,
        call the waitfunc before trying to get the task again.  If waitfunc is
        None and no tasks are available, return None.  If waitfunc raises a
        StopIteration, stop waiting for a task

        """
        obj = None
        sort = son.SON([
            ('priority', ming.DESCENDING),
            ('time_queue', ming.ASCENDING)])
        try:
            query = {'state': state}
            if only:
                query['task_name'] = {'$in': only}
            obj = cls.query.find_and_modify(
                query=query,
                update={
                    '$set': {
                        'state': 'busy',
                        'process': process
                    }
                },
                new=True,
                sort=sort)
        except pymongo.errors.OperationFailure, exc:
            if 'No matching object found' not in exc.args[0]:
                raise

        return obj

    @classmethod
    def event_loop(cls, waitfunc=None, process='worker', **kwargs):
        """Async event_loop that picks up tasks. Wait strategy determined by
        waitfunc

        """
        while True:
            if waitfunc is not None:
                waitfunc()
            yield cls.get(process=process, **kwargs)

    @classmethod
    def wait_for_tasks(cls, task_name=None, query=None, timeout=10000,
                       sleep_time=400):
        """
        Blocks until all tasks are complete or have errored out.

        @param task_name: If supplied, only wait on tasks that match this name.
        @param query: The ming query passed to L{MonQTask.query.find}
            defaults to { 'state': { '$in': ['ready', 'busy'] } }
        @param timeout: Raise exception if timeout is reached
        @param sleep_time: time to wait between requests

        @type task_name: str or None
        @type query: dict or None, query that finds INCOMPLETE tasks
        @type timeout: int
        @type sleep_time: int
        """
        if query is None:
            query = dict(
                state={'$in': ['ready', 'busy']}
            )
        if not isinstance(query, dict):
            raise TypeError("query must be a dict")

        if task_name is not None:
            query['task_name'] = task_name

        t = 0
        sess = session(cls)
        coll = sess.impl.bind.db[cls.__mongometa__.name]
        while coll.find(query).count():
            if t > timeout:
                raise Exception(
                    "Tasks did not complete before timeout: %s.",
                    ','.join(doc["task_name"] for doc in coll.find(query)))

            time.sleep(sleep_time / 1000.)
            t += sleep_time

    @classmethod
    def timeout_tasks(cls, older_than):
        """Mark all busy tasks older than a certain datetime as 'ready' again.
        Used to retry 'stuck' tasks."""
        spec = dict(state='busy')
        spec['time_start'] = {'$lt': older_than}
        cls.query.update(spec, {'$set': dict(state='ready')}, multi=True)

    @classmethod
    def clear_complete(cls):
        """Delete the task objects for complete tasks"""
        spec = dict(state='complete')
        cls.query.remove(spec)

    @classmethod
    def get_ready(cls):  # pragma no cover
        return cls.query.find(dict(state='ready')).all()

    @classmethod
    def run_ready(cls, worker=None):
        """Run all the tasks that are currently ready"""
        i = 0
        for i, task in enumerate(cls.get_ready()):
            task.process = worker
            task()
        return i

    def set_context(self):
        from vulcanforge.auth.model import User
        try:
            g.context_manager.set(
                self.context.project_id,
                app_config_id=self.context.app_config_id)
        except ForgeError:
            c.project = None
            c.app = None
        c.user = User.query.get(_id=self.context.user_id)

    def __call__(self, restore_context=True):
        """Call the task function with its context.  If restore_context is
        True,
        c.project/app/user will be restored to the values they had before this
        function was called.
        """
        self.time_start = datetime.utcnow()
        session(self.__class__).flush(self)
        LOG.info('%r', self)
        old_cproject = getattr(c, 'project', None)
        old_capp = getattr(c, 'app', None)
        old_cuser = getattr(c, 'user', None)
        try:
            func = self.function
            self.set_context()
            result = func(*self.args, **self.kwargs)
            state(self).session = session(self.__class__)
            self.result = result
            self.state = 'complete'
            return self.result
        except Exception, exc:
            LOG.exception('%r', self)
            self.state = 'error'
            if hasattr(exc, 'format_error'):
                self.result = exc.format_error()
                LOG.error(self.result)
            else:
                self.result = traceback.format_exc()
            raise
        finally:
            self.time_stop = datetime.utcnow()
            session(self.__class__).flush(self)
            if restore_context:
                c.project = old_cproject
                c.app = old_capp
                c.user = old_cuser

    def join(self, poll_interval=0.1):
        """Wait until this task is either complete or errors out, then return
        the result.

        """
        while self.state not in ('complete', 'error'):
            time.sleep(poll_interval)
            self.query.find(dict(_id=self._id), refresh=True).first()
        return self.result

    @classmethod
    def list(cls, state='ready'):
        """Print all tasks of a certain status to sys.stdout.  Used for
        debugging.

        """
        for t in cls.query.find(dict(state=state)):
            sys.stdout.write('%r\n' % t)
