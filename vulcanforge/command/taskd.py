import os
import signal
from datetime import datetime, timedelta

from vulcanforge.common.tasks import index as index_tasks
from vulcanforge.taskd import MonQTask
from vulcanforge.taskd.util import test_running_taskd
from vulcanforge.taskd.worker import TaskdWorker
from . import base


class TaskdCommand(base.Command):
    summary = 'Task server'
    parser = base.Command.standard_parser(verbose=True)
    parser.add_option('--only', dest='only', type='string', default=None,
                      help='only handle tasks of the given name(s) '
                           '(can be comma-separated list)')

    def command(self):
        self.basic_setup()
        self.log.info('taskd pid %s starting', os.getpid())
        self.keep_running = True
        self.restart_when_done = False
        self.worker = TaskdWorker(
            self.args[0].split("#")[0],
            name='%s pid %s' % (os.uname()[1], os.getpid()),
            only=self.options.only,
            log=self.log)
        signal.signal(signal.SIGHUP, self.worker.graceful_restart)
        signal.signal(signal.SIGTERM, self.worker.graceful_stop)
        signal.signal(signal.SIGUSR1, self.worker.log_current_task)
        # restore default behavior of not interrupting system calls
        # see http://docs.python.org/library/signal.html#signal.siginterrupt
        # and http://linux.die.net/man/3/siginterrupt
        signal.siginterrupt(signal.SIGHUP, False)
        signal.siginterrupt(signal.SIGTERM, False)
        signal.siginterrupt(signal.SIGUSR1, False)

        self.worker.event_loop()


class TaskCommand(base.Command):
    summary = 'Task command'
    parser = base.Command.standard_parser(verbose=True)
    parser.add_option('-s', '--state', dest='state', default='ready',
                      help='state of processes to examine')
    parser.add_option('-t', '--timeout', dest='timeout', type=int, default=60,
                      help='timeout (in seconds) for busy tasks')
    min_args = 2
    max_args = None
    usage = '<ini file> [list|retry|purge|timeout|commit|test]'

    def command(self):
        self.basic_setup()
        cmd = self.args[1]
        tab = dict(
            list=self._list,
            retry=self._retry,
            purge=self._purge,
            timeout=self._timeout,
            commit=self._commit,
            test=self._test)
        tab[cmd]()

    def _list(self):
        """List tasks"""

        self.log.info('Listing tasks of state %s', self.options.state)
        if self.options.state == '*':
            q = dict()
        else:
            q = dict(state=self.options.state)
        for t in MonQTask.query.find(q):
            print t

    def _retry(self):
        """Retry tasks in an error state"""

        self.log.info('Retry tasks in error state')
        MonQTask.query.update(
            dict(state='error'),
            {'$set': dict(state='ready')},
            multi=True)

    def _purge(self):
        """Purge completed tasks"""

        self.log.info('Purge complete/forget tasks')
        MonQTask.query.remove(
            dict(state='complete', result_type='forget'))

    def _timeout(self):
        """Reset tasks that have been busy too long to 'ready' state"""

        self.log.info(
            'Reset tasks stuck for %ss or more', self.options.timeout)
        cutoff = datetime.utcnow() - timedelta(seconds=self.options.timeout)
        MonQTask.timeout_tasks(cutoff)

    def _test(self):
        """Run a test task with optional timeout"""
        test_running_taskd(self.options.timeout)
        print "Taskd completed dummy task without incident"

    def _commit(self):
        """Schedule a SOLR commit"""

        self.log.info('Commit to solr')
        index_tasks.commit.post()
