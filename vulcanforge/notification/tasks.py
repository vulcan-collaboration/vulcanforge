import logging

from pylons import tmpl_context as c, app_globals as g
from bson import ObjectId

from vulcanforge.common.util import push_config
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


@task
def notify(n_id, ref_id, topic):
    from vulcanforge.notification.model import Mailbox
    Mailbox.deliver(n_id, ref_id, topic)
    Mailbox.fire_ready()


@task
def route_email(peer, mailfrom, rcpttos, data):
    """Route messages according to their destination:

    <topic>@<mount_point>.<project>.projects.vehicleforge.net
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
        except MailError, e:
            LOG.error('Error routing email to %s: %s', addr, e)
        except Exception:
            LOG.exception('Error routing mail to %s', addr)


@task
def sendmail(fromaddr, destinations, text, reply_to, subject, message_id,
             in_reply_to=None, html_text=None):
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
            addrs_plain.append(addr)
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
    plain_msg = encode_email_part(text, 'plain')
    if html_text is None:
        html_text = g.forge_markdown(email=True).convert(text)
    html_msg = encode_email_part(html_text, 'html')
    multi_msg = make_multipart_message(plain_msg, html_msg)
    log_emails = False
    if log_emails and len(addrs_multi):
        LOG.info(_LOG_MSG, fromaddr, addrs_multi, reply_to, subject, multi_msg)
    smtp_client.sendmail(
        addrs_multi, fromaddr, reply_to, subject, message_id, in_reply_to,
        multi_msg)
    if log_emails and len(addrs_plain):
        LOG.info(_LOG_MSG, fromaddr, addrs_plain, reply_to, subject, plain_msg)
    smtp_client.sendmail(
        addrs_plain, fromaddr, reply_to, subject, message_id,
        in_reply_to, plain_msg)
    if log_emails and len(addrs_html):
        LOG.info(_LOG_MSG, fromaddr, addrs_html, reply_to, subject, html_msg)
    smtp_client.sendmail(
        addrs_html, fromaddr, reply_to, subject, message_id, in_reply_to,
        html_msg)
