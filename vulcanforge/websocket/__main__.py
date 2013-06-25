# -*- coding: utf-8 -*-

"""
__main__

@author: U{tannern<tannern@gmail.com>}
"""
import os
import sys
from multiprocessing import Process
import gevent.baseserver
import gevent.monkey
from vulcanforge.websocket.server import make_server, get_config


def main():
    gevent.monkey.patch_all(dns=False)
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
        sys.stdout.write("starting Web Socket Server pid {}\n".format(
            os.getpid()))
        server = make_server(config, listener)
        server.serve_forever()
    listener = gevent.baseserver._tcp_listener((host, port))
    processes = []
    for i in max(0, range(process_count-1)):
        process = Process(target=start_server_process, args=(listener,))
        process.start()
        processes.append(process)
    sys.stdout.write("Serving at {} on port {}...\n".format(host, port))
    try:
        start_server_process(listener)
    except KeyboardInterrupt:
        sys.stdout.write("Server has been terminated\n")
        for process in processes:
            process.terminate()
    sys.exit(0)


if __name__ == '__main__':
    main()
