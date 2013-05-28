

class AuthMiddleware(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        import vulcanforge.auth.security_manager
        registry = environ['paste.registry']
        registry.register(
            vulcanforge.auth.credentials,
            vulcanforge.auth.security_manager.Credentials())
        return self.app(environ, start_response)