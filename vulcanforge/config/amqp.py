import logging

try:
    import kombu
except ImportError:
    kombu = None
from Queue import Queue

LOG = logging.getLogger(__name__)


class AMQPConnection(object):

    def __init__(self, hostname, port, userid, password, vhost):
        self._conn_proto = kombu.BrokerConnection(
            hostname=hostname,
            port=port,
            userid=userid,
            password=password,
            virtual_host=vhost)
        self._connection_pool = self._conn_proto.Pool(preload=1, limit=None)
        self.reset()

    def reset(self):
        self._conn = self._connection_pool.acquire()
        self.queue = self._conn.SimpleQueue('task')


class MockAMQ(object):

    def __init__(self, globals):
        self.globals = globals
        self.reset()

    def reset(self):
        self.queue = Queue()
