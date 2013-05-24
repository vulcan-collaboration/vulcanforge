import logging
import json
import sys
import re
import time
from urllib import unquote
from decorator import decorator

from ming.odm.odmsession import SessionExtension
from webob import exc
from webhelpers.html import literal, HTML
from pylons import tmpl_context as c
from tg.decorators import before_validate, before_call, before_render
from tg import request

LOG = logging.getLogger(__name__)


def _hook_breakpoint(remainder, params):
    raise Exception('Breakpoint')


break_before_validate = before_validate(_hook_breakpoint)
break_before_call = before_call(_hook_breakpoint)
break_before_render = before_render(_hook_breakpoint)


PROFILE_BLACKLIST = [
    re.compile(r'^/favicon\.(ico|gif|png|jpg)'),
    re.compile(r'^/error'),
    re.compile(r'.*/icon$'),
    re.compile(r'\.(js|css)$'),
    re.compile(r'^/_test_vars')
]


def time_action():
    """
    Decorator to time a tg controller action

    controller must subclass tg base controller

    Use like so:
    @time_action()
    def myaction(self...):
        ...
        c.log_time('Log Point 1')
        ...
        c.log_time('Log Point 2')
        ...
        return dict(...)

    will return:
    <table>
        <thead>
            <tr>
                <th>Log Point</th>
                <th>Total Elapsed</th>
                <th>Delta Elapsed</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Log Point 1</td>
                <td>x1 seconds</td>
                <td>y1 seconds</td>
            </tr>
            <tr>
                <td>Log Point 2</td>
                <td>x2 seconds</td>
                <td>y2 seconds</td>
            </tr>
            <tr>
                <td>Total</td>
                <td>x3 seconds</td>
                <td>y3 seconds</td>
            </tr>
        </tbody>
    </table>

    You get the idea.

    """
    def wrapper(func, controller, *args, **kwargs):
        # init timelogger
        logit = False
        if not getattr(c, 'log_time'):
            time_logger = TimeLog()
            time_logger.start()
            c.log_time = time_logger
            logit = True

        # run method and template
        method = getattr(controller, func.__name__)
        try:
            params, remainder = controller._remove_argspec_params_from_params(
                method, kwargs, [])
        except AttributeError:
            params, remainder = kwargs, args
        output = func(controller, *remainder, **dict(params))

        c.log_time('Pre-Render')
        try:
            response = controller._render_response(method, output)
        except AttributeError:
            # package specific
            from vulcanforge.common.controllers.base import (
                WsgiDispatchController)
            root = WsgiDispatchController()
            response = root._render_response(method, output)

        # cleanup
        c.log_time('Total')
        if logit:
            c.log_time.log_output()

            #        return HTML.html(
            #            HTML.body(
            #                HTML.frameset(
            #                    HTML.frame(
            #                        HTML.html(
            #                            HTML.body(c.log_time.render_html())
            #                        )
            #                    ) +\
            #                    HTML.frame(
            #                        HTML.html(
            #                            HTML.body(response)
            #                        )
            #                    )
            #                )
            #            )
            #        )

    return decorator(wrapper)


class TimeLog(object):
    """Callable object for logging times for benchmarking"""
    def __init__(self, title=None):
        self.n = 1
        self.t0 = self.t1 = None
        self.log = []
        self.title = title
        self.has_manual = False

    def start(self):
        self.t0 = self.t1 = time.time()

    def __call__(self, name=None, manual=True):
        if name is None:
            name = str(self.n)
        now = time.time()
        self.log.append((name, now - self.t1, now - self.t0))
        self.t1 = now
        self.n += 1
        if manual:
            self.has_manual = True

    def log_output(self):
        name_width = max(len(li[0]) for li in self.log) + 2
        num_width = 8
        total_width = name_width + num_width * 2 + 3
        if self.title:
            LOG.info(u'{:*^{total_width}}'.format(
                ' ' + self.title + ' ',
                total_width=total_width
            ))
        format_str = u'|{:^{name_width}}|{:^{num_width}}|{:^{num_width}}|'
        LOG.info(format_str.format(
            u"Log Pt",
            u"dT",
            u"T",
            name_width=name_width,
            num_width=num_width
        ))
        LOG.info(u'-' * total_width)
        format_str = u'|{:{name_width}}|{:{num_width}.4f}|{:{num_width}.4f}|'
        for name, dt, t in self.log:
            LOG.info(format_str.format(
                name,
                dt,
                t,
                name_width=name_width,
                num_width=num_width
            ))
        LOG.info(u'-' * total_width)

    def render_html(self):
        def render_row(row):
            return HTML.tr(
                HTML.td(row[0]) +\
                HTML.td('%0.4f' % row[1]) +\
                HTML.td('%0.4f' % row[2])
            )
        style = ';'.join((
            'position:absolute',
            'left: 35%',
            'top: 0',
            'z-index: 10000000',
            'background-color: #fff',
            'border: 1px solid #333;'
            ))
        html = HTML.table(
            HTML.thead(
                HTML.tr(
                    HTML.th('Log Point') +\
                    HTML.th('Delta Elapsed (s)') +\
                    HTML.th('Total Elapsed (s)')
                )
            ) +\
            HTML.tbody(
                literal('').join(map(render_row, self.log))
            ), style=style)
        return html


def profile_setup_request():
    # determine whether we want to profile
    path = request.environ['PATH_INFO']
    for p in PROFILE_BLACKLIST:
        if p.match(path):
            c.profiler_engaged = False
            break
    else:
        c.profiler_engaged = True

    time_logger = TimeLog(path)
    time_logger.start()
    c.log_time = time_logger


def profile_before_call(remainder, params):
    if getattr(c, 'profiler_engaged', False):
        c.log_time('Post-Validation', False)


def profile_before_render(remainder, params, output):
    if getattr(c, 'profiler_engaged', False):
        c.log_time('Pre-Render', False)


def profile_after_render(response):
    if getattr(c, 'profiler_engaged', False) and c.log_time.has_manual:
        c.log_time('Finish', False)
        c.log_time.log_output()


def profile_dne(remainder, params):
    def dne(name):
        LOG.error('Profiler called with log point %s', name)
    c.log_time = dne


class log_action(object):  # pragma no cover

    def __init__(self,
                 logger=None,
                 level=logging.INFO,
                 msg=None,
                 *args, **kwargs):
        if logger is None:
            logger = logging
        self._logger = logger
        self._level = level
        self._msg = msg
        self._args = args
        self._kwargs = kwargs
        self._extra_proto = dict(
            user=None,
            user_id=None,
            source=None,
            project_name=None,
            group_id=None)

    def __call__(self, func):
        self._func = func
        self._extra_proto.update(action=func.__name__)
        if self._msg is None:
            self._msg = func.__name__
        result = lambda *args, **kwargs: self._wrapper(*args, **kwargs)
        # assert not hasattr(func, 'decoration')
        if hasattr(func, 'decoration'):
            result.decoration = func.decoration
        return result

    def _wrapper(self, *args, **kwargs):
        result = None
        try:
            try:
                result = self._func(*args, **kwargs)
            except exc.HTTPServerError:
                raise
            except exc.HTTPException, e:
                result = e
            args = self._args
            kwargs = self._kwargs
            extra = kwargs.setdefault('extra', {})
            extra.update(self._make_extra(result))
            self._logger.log(self._level, self._msg,
                *self._args, **self._kwargs)
            return result
        except:
            args = self._args
            kwargs = self._kwargs
            extra = kwargs.setdefault('extra', {})
            extra.update(self._make_extra(result))
            kwargs['exc_info'] = sys.exc_info()
            self._logger.log(logging.ERROR, self._msg,
                *self._args, **self._kwargs)
            raise

    def _make_extra(self, result=None):
        """
        Create a dict of extra items to be added to a log record
        """
        extra = self._extra_proto.copy()
        # Save the client IP address
        client_ip = request.headers.get('X_FORWARDED_FOR', request.remote_addr)
        client_ip = client_ip.split(',')[0].strip()
        extra.update(client_ip=client_ip)
        # Save the user info
        user = getattr(request, 'user', None)
        if user:
            extra.update(user=user.username,
                user_id=user.id)
            # Save the project info
        if (result
            and isinstance(result, dict)
            and 'p' in result
            and result['p'] is not None):
            extra.update(
                source=result['p']['source'],
                project_name=result['p']['shortname'],
                group_id=result['p'].get('sf_id'))
            # Log the referer cookie if it exists
        referer_link = request.cookies.get('referer_link')
        if referer_link:
            referer_link = unquote(referer_link)
            try:
                referer_link = json.loads(referer_link)
            except ValueError:
                pass
        extra['referer_link'] = referer_link
        return extra


class PostEventsSessionExtension(SessionExtension):
    def __init__(self, session):
        SessionExtension.__init__(self, session)

    @staticmethod
    def _get_topic(obj, topic):
        return '{}{}'.format(obj.__class__.__name__, topic)

    def before_insert(self, obj, st):
        topic = self._get_topic(obj, '_before_insert')
        LOG.debug('event: %s', topic)
        #g.post_event(topic, _id=getattr(obj, '_id', None))

    def after_insert(self, obj, st):
        topic = self._get_topic(obj, '_after_insert')
        LOG.debug('event: %s', topic)
        #g.post_event(topic, _id=getattr(obj, '_id', None))

    def before_update(self, obj, st):
        topic = self._get_topic(obj, '_before_update')
        LOG.debug('event: %s', topic)
        #g.post_event(topic, _id=getattr(obj, '_id', None))

    def after_update(self, obj, st):
        topic = self._get_topic(obj, '_after_update')
        LOG.debug('event: %s', topic)
        #g.post_event(topic, _id=getattr(obj, '_id', None))

    def before_delete(self, obj, st):
        topic = self._get_topic(obj, '_before_delete')
        LOG.debug('event: %s', topic)
        #g.post_event(topic, _id=getattr(obj, '_id', None))

    def after_delete(self, obj, st):
        topic = self._get_topic(obj, '_after_delete')
        LOG.debug('event: %s', topic)
        #g.post_event(topic, _id=getattr(obj, '_id', None))

    def before_remove(self, cls, *args, **kwargs):
        topic = '{}_before_remove'.format(cls.__name__)
        LOG.debug('event: %s', topic)
        #g.post_event(topic, *args, **kwargs)

    def after_remove(self, cls, *args, **kwargs):
        topic = '{}_after_remove'.format(cls.__name__)
        LOG.debug('event: %s', topic)
        #g.post_event(topic, *args, **kwargs)

    def before_flush(self, obj=None):
        if not obj:
            return
        topic = self._get_topic(obj, '_before_flush')
        LOG.debug('event: %s', topic)
        #g.post_event(topic, _id=getattr(obj, '_id', None))

    def after_flush(self, obj=None):
        if not obj:
            return
        topic = self._get_topic(obj, '_after_flush')
        LOG.debug('event: %s', topic)
        #g.post_event(topic, _id=getattr(obj, '_id', None))
