# -*- coding: utf-8 -*-

"""
__main__

@author: U{tannern<tannern@gmail.com>}
"""
import gevent
import gevent.monkey

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
    listener = gevent.baseserver._tcp_listener((host, port))
    processes = []
    for i in range(process_count):
        process = Process(target=start_server_process, args=(listener,))
        process.start()
        processes.append(process)
    LOG.info("Serving at {} on port {}...".format(host, port))
    try:
        while True:
            sleep(10)
    except KeyboardInterrupt:
        LOG.info("Stopping server...")
        for process in processes:
            process.terminate()
        for process in processes:
            process.join()
        raise
    finally:
        LOG.info("Server has been terminated")
        sys.exit(0)


if __name__ == '__main__':
    main()
