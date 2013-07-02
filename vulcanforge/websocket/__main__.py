# -*- coding: utf-8 -*-

"""
__main__

@author: U{tannern<tannern@gmail.com>}
"""
from time import sleep
import gevent
import gevent.monkey

gevent.monkey.patch_all(dns=False)
import os
import sys
from multiprocessing import Process
import gevent.baseserver
from vulcanforge.websocket import get_config
from vulcanforge.websocket.server import make_server


def main():
    try:
        config_path = sys.argv[1]
    except IndexError:
        sys.stderr.write("expected path to config file as first argument\n")
        sys.exit(1)
    config = get_config(config_path)
    if not config:
        sys.stderr.write("could not load file config at {}\n".format())
        sys.exit(2)
    host = config['websocket.host']
    port = int(config['websocket.port'])
    process_count = int(config['websocket.process_count'])
    sys.stdout.write("starting {} server processes...\n".format(process_count))

    def start_server_process(listener):
        gevent.reinit()
        sys.stdout.write("starting Web Socket Worker process: pid {}\n"
                         "".format(os.getpid()))
        server = make_server(config, listener)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            sys.stdout.write("stopping Web Socket Worker process: pid {}\n"
                             "".format(os.getpid()))
            sys.exit(0)
    listener = gevent.baseserver._tcp_listener((host, port))
    processes = []
    for i in range(process_count):
        process = Process(target=start_server_process, args=(listener,))
        process.start()
        processes.append(process)
    sys.stdout.write("Serving at {} on port {}...\n".format(host, port))
    try:
        while True:
            sleep(10)
    except KeyboardInterrupt:
        sys.stdout.write("Stopping server...\n")
        for process in processes:
            process.terminate()
        for process in processes:
            process.join()
        raise
    finally:
        sys.stdout.write("Server has been terminated\n")
        sys.exit(0)


if __name__ == '__main__':
    main()
