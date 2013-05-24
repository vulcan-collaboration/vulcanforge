import bson
from pylons import app_globals as g, tmpl_context as c
from tg import flash, redirect
from tg.decorators import with_trailing_slash, expose

from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import (
    require_post,
    validate_form
)
from vulcanforge.auth.oauth.model import OAuthConsumerToken
from vulcanforge.auth.oauth.forms import OAuthApplicationForm

TEMPLATE_DIR = 'jinja:vulcanforge:auth/oauth/templates/'


class OAuthController(BaseController):

    class Forms(BaseController.Forms):
        oauth_application_form = OAuthApplicationForm(action='register')

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'oauth_applications.html')
    def index(self, **kw):
        g.security.require_authenticated()
        c.form = self.Forms.oauth_application_form
        return dict(apps=OAuthConsumerToken.for_user(c.user))

    @expose()
    @require_post()
    @validate_form("oauth_application_form", error_handler=index)
    def register(self, application_name=None, application_description=None,
                 **kw):
        g.security.require_authenticated()
        OAuthConsumerToken(
            name=application_name,
            description=application_description
        )
        flash('OAuth Application registered')
        redirect('.')

    @expose()
    @require_post()
    def delete(self, id=None):
        g.security.require_authenticated()
        app = OAuthConsumerToken.query.get(_id=bson.ObjectId(id))
        if app is None:
            flash('Invalid app ID', 'error')
            redirect('.')
        if app.user_id != c.user._id:
            flash('Invalid app ID', 'error')
            redirect('.')
        app.delete()
        flash('Application deleted')
        redirect('.')
