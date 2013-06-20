# -*- coding: utf-8 -*-

"""
__main__

@author: U{tannern<tannern@gmail.com>}
"""
import sys
import gevent.monkey
from vulcanforge.websocket.server import make_server, get_config


if __name__ == '__main__':
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
    host = config['host']
    port = config['port']
    server = make_server(config)
    sys.stdout.write("Serving Web Sockets at {} on port {}...\n".format(host,
                                                                        port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("Server has been terminated\n")
    sys.exit(0)
