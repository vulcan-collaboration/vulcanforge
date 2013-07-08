# -*- coding: utf-8 -*-

"""
__main__

@author: U{tannern<tannern@gmail.com>}
"""
import gevent
import gevent.monkey
import signal

gevent.monkey.patch_all(dns=False)
import logging
import os
import sys
from time import sleep
from multiprocessing import Process
import gevent.baseserver
from vulcanforge.websocket import get_config
from vulcanforge.websocket.server import make_server


logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("vulcanforge.websocket")


def main():
    try:
        config_path = sys.argv[1]
    except IndexError:
        LOG.info("expected path to config file as first argument")
        sys.exit(1)
    config = get_config(config_path)
    if not config:
        LOG.info("could not load file config at {}".format())
        sys.exit(2)
    host = config['websocket.host']
    port = int(config['websocket.port'])
    process_count = int(config['websocket.process_count'])
    LOG.info("starting {} server processes...".format(process_count))

    def start_server_process(listener):
        gevent.reinit()
        LOG.info("starting Web Socket Worker process: pid {}"
                 "".format(os.getpid()))
        server = make_server(config, listener)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            LOG.info("stopping Web Socket Worker process: pid {}\n"
                     "".format(os.getpid()))
            sys.exit(0)
    listener = gevent.baseserver._tcp_listener((host, port), reuse_addr=1)
    processes = []
    for i in range(process_count):
        process = Process(target=start_server_process, args=(listener,))
        process.start()
        processes.append(process)
    LOG.info("Serving at {} on port {}...".format(host, port))

    def cleanup_and_quit():
        LOG.info("Stopping server...")
        for process in processes:
            process.terminate()
        for process in processes:
            process.join()
        listener.close()
        LOG.info("Server has been terminated")
        sys.exit(0)
    signal.signal(signal.SIGHUP, cleanup_and_quit)
    signal.signal(signal.SIGTERM, cleanup_and_quit)
    # restore default behavior of not interrupting system calls
    # see http://docs.python.org/library/signal.html#signal.siginterrupt
    # and http://linux.die.net/man/3/siginterrupt
    signal.siginterrupt(signal.SIGHUP, False)
    signal.siginterrupt(signal.SIGTERM, False)
    try:
        while True:
            sleep(1)  # todo: join process pool with timeout instead of sleep
    except KeyboardInterrupt:
        pass
    finally:
        cleanup_and_quit()


if __name__ == '__main__':
    main()
