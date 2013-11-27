# -*- coding: utf-8 -*-

"""
eventd

@author: U{tannern<tannern@gmail.com>}
"""
import os
import signal

from . import base
from vulcanforge.eventd.worker import EventdWorker


class EventdCommand(base.Command):
    summary = 'Event server'
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        self.log.info('eventd pid %s starting', os.getpid())
        self.keep_running = True
        self.restart_when_done = False
        self.worker = EventdWorker(self.args[0].split("#")[0], log=self.log)

        signal.signal(signal.SIGHUP, self.worker.graceful_restart)
        signal.signal(signal.SIGTERM, self.worker.graceful_stop)
        # restore default behavior of not interrupting system calls
        # see http://docs.python.org/library/signal.html#signal.siginterrupt
        # and http://linux.die.net/man/3/siginterrupt
        signal.siginterrupt(signal.SIGHUP, False)
        signal.siginterrupt(signal.SIGTERM, False)

        self.worker.event_loop()
