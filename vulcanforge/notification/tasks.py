import logging
import os

import email
import jinja2
from BeautifulSoup import BeautifulSoup
from tg import config
from pylons import tmpl_context as c, app_globals as g
from bson import ObjectId
from email.mime.image import MIMEImage

from vulcanforge.common.util import push_config
from vulcanforge.common.util.filesystem import module_resource_path
from vulcanforge.taskd import task
from .util import (
    SMTPClient,
    parse_address,
    parse_message,
    identify_sender,
    isvalid,
    encode_email_part,
    make_multipart_message
)
from .exceptions import MailError

LOG = logging.getLogger(__name__)
_LOG_MSG = """
"sending multi mails...
\tfrom: %s
\tto: %s
\treply_to: %s
\tsubject: %s
### begin mail ###
%s
### end mail ###"
"""

smtp_client = SMTPClient()
class LogoSingleton(object):
    mime_images = {}


def branding_logo():
    if hasattr(LogoSingleton, 'branding_logo'):
        return LogoSingleton.branding_logo
    else:
        try:
            branding_logo_path = module_resource_path(config.get('forgemail.branding_logo', ''))
            if branding_logo_path and os.path.exists(branding_logo_path):
                with open(branding_logo_path, 'rb') as fp:
                    branding_logo = MIMEImage(fp.read())
                    branding_logo.add_header('Content-ID', '<branding_logo>')
                    branding_logo.add_header(
                        'Content-Disposition',
                        'inline; filename={}'.format(
                            os.path.basename(branding_logo_path))
                    )
                    setattr(LogoSingleton, 'branding_logo', branding_logo)
                    return branding_logo
        except:
            setattr(LogoSingleton, 'branding_logo', None)


def mime_image(cid, path):
    if LogoSingleton.mime_images.has_key(cid):
        return LogoSingleton.mime_images[cid]
    else:
        try:
            if path and os.path.exists(path):
                with open(path, 'rb') as fp:
                    mime_image = MIMEImage(fp.read())
                    mime_image.add_header('Content-ID', cid)
                    mime_image.add_header(
                        'Content-Disposition',
                        'inline; filename={}'.format(
                            os.path.basename(path))
                    )
                    LogoSingleton.mime_images[cid] = mime_image
                    return mime_image
        except:
            LogoSingleton.mime_images[cid] = None

@task
def notify(n_id, ref_id, topic):
    from vulcanforge.notification.model import Mailbox
    Mailbox.deliver(n_id, ref_id, topic)
    Mailbox.fire_ready()


@task
def route_email(peer, mailfrom, rcpttos, data):
    """Route messages according to their destination:

    <topic>@<mount_point>.<project>.projects.vulcanforge.net
    gets sent to c.app.handle_message(topic, message)

    """
    try:
        msg = parse_message(data)
    except Exception:  # pragma no cover
        LOG.exception('Parse Error: (%r,%r,%r)', peer, mailfrom, rcpttos)
        return
    c.user = identify_sender(peer, mailfrom, msg['headers'], msg)
    LOG.info('Received email from %s', c.user.username)
    # For each of the addrs, determine the project/app and route appropriately
    for addr in rcpttos:
        try:
            userpart, project, app = parse_address(addr)
            with push_config(c, project=project, app=app):
                if not app.has_access(c.user, userpart):
                    LOG.info('Access denied for %s to mailbox %s',
                             c.user, userpart)
                else:
                    if msg['multipart']:
                        msg_hdrs = msg['headers']
                        for part in msg['parts']:
                            ctype = part.get('content_type', '')
                            if ctype.startswith('multipart/'):
                                continue
                            msg = dict(
                                headers=dict(msg_hdrs, **part['headers']),
                                message_id=part['message_id'],
                                in_reply_to=part['in_reply_to'],
                                references=part['references'],
                                filename=part['filename'],
                                content_type=ctype,
                                payload=part['payload'])
                            c.app.handle_message(userpart, msg)
                    else:
                        c.app.handle_message(userpart, msg)
        except MailError as e:
            LOG.error('Error routing email to %s: %s', addr, e)
        except Exception:
            LOG.exception('Error routing mail to %s', addr)


@task
def sendmail(fromaddr, destinations, text, reply_to, subject, message_id,
             in_reply_to=None,
             title_html=None,
             html_text=None,
             artifact_html='',
             footer_html='',
             mime_images={}):
    from vulcanforge.auth.model import User
    addrs_plain = []
    addrs_html = []
    addrs_multi = []
    if '@' not in fromaddr:
        user = User.query.get(_id=ObjectId(fromaddr))
        if not user:
            LOG.warning('Cannot find user with ID %s', fromaddr)
            # TODO: forgemail reference follows
            fromaddr = 'noreply@in.vulcanforge.org'
        else:
            fromaddr = user.email_address_header()

    # Divide addresses based on preferred email formats
    for addr in destinations:
        if isinstance(addr, basestring) and isvalid(addr):
            addrs_multi.append(addr)
        else:
            try:
                user = User.query.get(_id=ObjectId(addr))
                if not user:
                    LOG.warning('Cannot find user with ID %s', addr)
                    continue
            except:
                LOG.exception('Error looking up user with ID %r')
                continue
            addr = user.email_address_header()
            if not addr and user.email_addresses:
                addr = user.email_addresses[0]
                LOG.warning(
                    'User %s has not set primary email address, using %s',
                    user._id, addr)
            if not addr:
                LOG.error(
                    "User %s has not set any email address, can't deliver",
                    user.username)
                continue
            if user.get_pref('email_format') == 'plain':
                addrs_plain.append(addr)
            elif user.get_pref('email_format') == 'html':
                addrs_html.append(addr)
            else:
                addrs_multi.append(addr)

    # sanitize reply_to for no forgemail returns and fussy mail delivery agents
    if reply_to:
        h = email.header.Header()
        h.append(g.forgemail_return_path)
        reply_to = h
    if html_text is None:
        html_text = g.forge_markdown(email=True).convert(text)

    try:
        template_dir = config.get('notification.templates',
                                  'vulcanforge.notification')
        templates = jinja2.Environment(
            loader=jinja2.PackageLoader(template_dir, 'templates'))
        email_template = templates.get_template('mail/email.html')
        context = {
            'branding_logo': branding_logo(),
            'title_html': title_html,
            'body_html': html_text,
            'artifact_html': g.forge_markdown(email=True).convert(artifact_html),
            'footer_html': g.forge_markdown(email=True).convert(footer_html)
        }
        full_email_html = email_template.render(context)
        # Remove unnecessary white spaces
        full_email_html = os.linesep.join(
            [s.strip() for s in full_email_html.splitlines() if s.strip()])
    except Exception:
        full_email_html = html_text

    plain_text = ''.join(BeautifulSoup(html_text).findAll(text=True))
    plain_msg = encode_email_part(plain_text, 'plain')
    html_msg = encode_email_part(full_email_html, 'html')

    images = []
    for cid in mime_images.keys():
        mime_image_path = mime_images[cid]
        mime_img = mime_image(cid, mime_image_path)
        if mime_img:
            images.append(mime_img)

    if branding_logo() is not None:
        images.append(branding_logo())

    msg_parts = [plain_msg, html_msg, images]
    multi_msg = make_multipart_message(*msg_parts)

    if addrs_multi:
        smtp_client.sendmail(
            addrs_multi, fromaddr, reply_to, subject, message_id, in_reply_to,
            multi_msg)
    if addrs_plain:
        smtp_client.sendmail(
            addrs_plain, fromaddr, reply_to, subject, message_id,
            in_reply_to, plain_msg)
    if addrs_html:
        smtp_client.sendmail(
            addrs_html, fromaddr, reply_to, subject, message_id, in_reply_to,
            multi_msg)

    log_emails = False
    if log_emails:
        if len(addrs_multi):
            LOG.info(_LOG_MSG, fromaddr, addrs_multi, reply_to, subject,
                     multi_msg)
        if len(addrs_plain):
            LOG.info(_LOG_MSG, fromaddr, addrs_plain, reply_to, subject,
                     plain_msg)
        if len(addrs_html):
            LOG.info(_LOG_MSG, fromaddr, addrs_html, reply_to, subject,
                     multi_msg)
