Component Services
==================

An application built on the Vulcan framework uses the following component
services:

.. graphviz:: component_services.dot

Dependencies
------------

MongoDB Document Store
^^^^^^^^^^^^^^^^^^^^^^

`MongoDB`_ is used as the primary document store and is primarily accessed
through the `Ming ODM`_.

This service is horizontally scalable using replication.

.. _MongoDB: http://www.mongodb.org
.. _Ming ODM: http://merciless.sourceforge.net/odm.html

SOLR Index
^^^^^^^^^^

The `SOLR`_ index allows for significantly faster lookups and in some cases
precaching of views over going straight to the MongoDB database.

.. _SOLR: http://lucene.apache.org/solr/

Redis Object Store
^^^^^^^^^^^^^^^^^^

`Redis`_ is used for caching, pub/sub communication, and queueing between
services.

This service is horizontally scalable using replication.

.. _Redis: http://redis.io/

Swift/S3 Object Store
^^^^^^^^^^^^^^^^^^^^^

`Swift`_, or another `S3`_ API compatible object store, is used for storing and
serving files.

.. _Swift: http://swift.openstack.org/
.. _S3: http://aws.amazon.com/s3/

SMTP Email Service
^^^^^^^^^^^^^^^^^^

An SMTP server must be present to send emails. Typically this is `Exim`_.

.. _Exim: http://www.exim.org/

Vulcan Services
---------------

.. toctree::

    forgeapp
    taskd
    eventd
    websocketapp
