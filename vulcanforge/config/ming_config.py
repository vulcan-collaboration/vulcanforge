import logging
import time

from paste.deploy.converters import asbool
from formencode import validators
from formencode.variabledecode import variable_decode
from pymongo import ReadPreference
from pymongo.errors import AutoReconnect
from ming.datastore import create_datastore, create_engine
from ming.session import Session
from ming.config import DatastoreSchema

LOG = logging.getLogger(__name__)


class ReadPreferenceValidator(validators.OneOf):
    list = ['PRIMARY', 'SECONDARY', 'SECONDARY_ONLY']
    validate_python = validators.OneOf._validate_noop

    def validate_other(self, value, state):
        return validators.OneOf.validate_python(self, value, state)

    def _to_python(self, value, state=None):
        if value:
            return getattr(ReadPreference, value)


class ReplicantDatastoreSchema(DatastoreSchema):
    """Schema for Replica Set config"""
    replica_set = validators.UnicodeString(if_missing=None)
    read_preference = ReadPreferenceValidator(
        if_missing=ReadPreference.PRIMARY)


def wait_for_ming_connection(bind, max_timeout=15 * 60):
    failures = 0
    sleep_time = 1.
    conn = None

    while sleep_time < max_timeout:
        try:
            conn = bind.conn
        except AutoReconnect:
            pass

        if conn:
            break

        sleep_time *= 1.5
        failures += 1
        LOG.critical('Ming AutoReconnect Failure {}'.format(failures))
        time.sleep(sleep_time)


def ming_replicant_configure(**kwargs):
    """
    modeled after configure in `ming.config.py`

    """
    config = variable_decode(kwargs)
    datastores = {}
    for name, ds_config in config['ming'].iteritems():
        block = asbool(ds_config.pop('block', 'false'))
        ds_kwargs = ReplicantDatastoreSchema.to_python(ds_config, None)
        replica_set = ds_kwargs.pop('replica_set', None)
        if replica_set:
            ds_kwargs['replicaSet'] = replica_set
        database = ds_kwargs.pop('database', None)
        uri = ds_kwargs.pop('uri', None)
        if uri:
            authenticate = ds_kwargs.pop('authenticate', None)
            bind = create_engine(uri, **ds_kwargs)
            datastores[name] = create_datastore(
                database, bind=bind, authenticate=authenticate)
        else:
            datastores[name] = create_datastore(database, **ds_kwargs)

        # block until connection achieved
        if block:
            wait_for_ming_connection(datastores[name].bind)

    Session._datastores = datastores
    # bind any existing sessions
    for name, session in Session._registry.iteritems():
        session.bind = datastores.get(name, None)
