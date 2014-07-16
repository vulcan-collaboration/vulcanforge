Configuration Files
===================

Vulcan applications are `TurboGears`_ applications and use
`TurboGears congifuration files`_ which are similar to Microsoft Windows INI
files and are compatible with the Python standard library's `ConfigParser`_. The
config file specifies service addresses & credentials, platform options, and
extensions/overrides.

Sections
--------

Some section inheritance is supported with ``use = <PARENT_SECTION_NAME>``.

``[DEFAULT]``
^^^^^^^^^^^^^

Parameters defined here are inherited in all sections unless explicitly
overridden.

:debug: Boolean stating if debug mode is enabled. **This should always be
    false in production!** Setting this to ``true`` will enable an
    interactive debugging console on errors which is a security vulnerability in
    a production deployment but a valuable tool during development.

``[server:main]``
^^^^^^^^^^^^^^^^^

This section defines server parameters for running the Vulcan application.

:host: The IP address to serve the Vulcan application on (0.0.0.0 for all)
:port: The port to bind to the Vulcan application (80 for HTTP)

``[app:myapp]``
^^^^^^^^^^^^^^^

::

    use = egg:MyAppClass

This section is used by and named for your Vulcan TurboGears application and is
where the majority of parameters will be set.

``[app:myapp_test]``
^^^^^^^^^^^^^^^^^^^^

::

    # inherit from [app:myapp]
    use = myapp

This section is used when running tests and is useful to set up alternate
service locations and databases for test data.

``[app:taskd]``
^^^^^^^^^^^^^^^

::

    # inherit from [app:myapp]
    use = myapp

    # set root controller to the task controller
    override_root = task

``[app:event]``
^^^^^^^^^^^^^^^

::

    # inherit from [app:myapp]
    use = myapp

    # set root controller to the event controller
    override_root = event

``[websocketserver]``
^^^^^^^^^^^^^^^^^^^^^

This section is used by the `websocketapp` but websocket settings can be set in
the ``[DEFAULT]`` section.


Platform Services
-----------------

Many of these settings are used in different sections by different services
and can be defined in the ``[DEFAULT]`` section only once instead.

Taskd
^^^^^

:monq.poll_interval: Interval to poll for new tasks if using polling instead of
    a Redis queue.
:task_queue.host: The Redis host to use for the task queue
:task_queue.port:
:task_queue.cls: :py:class:`vulcanforge.taskd.queue:RedisQueue`

WebSocket
^^^^^^^^^

:websocket.enabled: Boolean stating whether websockets should be enabled for
    this platform.
:websocket.host: The IP address to bind the Vulcan Websocket service to
:websocket.port: The port to bind the Vulcan Websocket service to
:websocket.auth_api_root: Vulcan app api root. This is the URL where the
    websocket service will authenticate and authorize with the Vulcan
    application. Here should be mounted
    :py:class:`vulcanforge.websocket.controllers.WebSocketAPIController` or it's
    subclass.

SMTP/Email
^^^^^^^^^^

:smtp_server: SMTP service host location (i.e. 127.0.0.1 or smtp.example.com)
:smtp_port: SMTP service host port
:forgemail.host:
:forgemail.port:
:forgemail.domain:
:forgemail.url:
:forgemail.return_path:

Redis
^^^^^

:redis.host: Redis service host location
:redis.port: Redis service host port

S3/Swift
^^^^^^^^

:s3.enabled: Boolean stating whether S3/Swift is available for this platform.
:s3.connect_string:
:s3.password:
:s3.ip_address:
:s3.port:
:s3.ssl:
:s3.bucket_name:
:s3.tempurlkey:
:s3.account_name:
:s3.app_prefix:
:s3.prefix:
:swift.serve_local: Boolean stating if resources should be served through a
    proxy on the Vulcan deployment. This should only be set ``true`` if the S3
    server is set up to be not directly accessible to end users.
:swift.auth.deployment_id:
:swift.auth.deployment_param:
:swift.auth.token:
:swift.auth.token_param:

Mongodb
^^^^^^^

Credentials and settings for the Mongodb connection through `Ming`_.

:ming.main.uri:
:ming.main.database:
:ming.main.replica_set:
:ming.main.read_preference:
:ming.main.auto_ensure_indexes:

:ming.project.uri:
:ming.project.database:
:ming.project.replica_set:
:ming.project.read_preference:
:ming.project.auto_ensure_indexes:

Solr
^^^^

:solr.host: Solr service location
:solr.port: Solr service port
:solr.vulcan.core: Identifier of the vulcan Solr core

API Services
------------

These are API credentials for web services used in an application.

ReCaptcha
^^^^^^^^^

:recaptcha_api_url: www.google.com/recaptcha/api
:recaptcha_public_key:
:recaptcha_private_key:

Platform Options
----------------

:theme: The theme to use. See `themes`.

Passwords/User Authentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:login_lock.engaged: Boolean stating if failed login attempts lock a user
    account
:login_lock.num: Number of failed attempts that trigger a lock
:login_lock.interval: Duration of time in minutes that failed login attempts
    count towards an account lock
:auth.user.inactivity_period: Time in months, more precisely 30 day periods,
    after which an account with no activity is considered inactive and will be
    disabled with the ``paster expire-users <config>`` command

:auth.pw.min_length: minimum password length

:auth.pw.lifetime.months: Password lifetime after which a user required to
    change their password
:auth.pw.min_lifetime.hours: Span of time in hours after a password change
    during which the password cannot be changed again
:auth.pw.generations: Number of old passwords that cannot be reused
:auth.pw.min_levenshtein: Minimum `levenshtein distance`_ allowed between
    consecutive passwords

:idle_logout_enabled: Boolean whether users should be logged out automatically
    after a period of inactivity
:idle_logout_minutes: Span of time in minutes after which a user should be
    logged out automatically if ``idle_logout_enabled`` is true
:idle_logout_countdown_seconds: Span of time in seconds before automatic logout
    when a user is presented with a dialog to cancel the automatic logout


.. _TurboGears: http://turbogears.org/
.. _TurboGears congifuration files: https://turbogears.readthedocs.org/en/rtfd2.2.2//main/Config.html
.. _ConfigParser: https://docs.python.org/2/library/configparser.html
.. _levenshtein distance: http://en.wikipedia.org/wiki/Levenshtein_distance
.. _Ming: http://merciless.sourceforge.net/tour.html
