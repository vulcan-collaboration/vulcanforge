import re
import logging
import smtplib
import email.feedparser
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email import header

import tg
from paste.deploy.converters import asbool, asint
from formencode import validators as fev
from pylons import tmpl_context as c

from vulcanforge.common.util import ConfigProxy, push_config, nonce
from .exceptions import AddressException

LOG = logging.getLogger(__name__)

RE_MESSAGE_ID = re.compile(r'<(.*)>')
config = ConfigProxy(
    common_suffix='forgemail.domain',
    return_path='forgemail.return_path')
EMAIL_VALIDATOR=fev.Email(not_empty=True)


def gen_message_id():
    if getattr(c, 'project', False):
        parts = c.project.url().split('/')[1:-1]
    else:
        parts = ['mail']
    if getattr(c, 'app', False):
        addr = '%s.%s' % (nonce(40), c.app.config.options['mount_point'])
    else:
        addr = nonce(40)
    base_addr = tg.config.get('forgemail.domain', ".vulcanforge.org")
    return '%s@%s%s' % (addr, '.'.join(reversed(parts)), base_addr)


def Header(text, charset):
    """Helper to make sure we don't over-encode headers

    (gmail barfs with encoded email addresses.)

    """
    if isinstance(text, header.Header):
        return text
    hdr = header.Header('', charset)
    for word in text.split(' '):
        hdr.append(word)
    return hdr


def parse_address(addr):
    from vulcanforge.project.model import Project
    userpart, domain = addr.split('@')
    # remove common domain suffix
    if not domain.endswith(config.common_suffix):
        raise AddressException, 'Unknown domain: ' + domain
    domain = domain[:-len(config.common_suffix)]
    path = '/'.join(reversed(domain.split('.')))
    project, mount_point = Project.by_url_path('/' + path)
    if project is None:
        raise AddressException, 'Unknown project: ' + domain
    if len(mount_point) != 1:
        raise AddressException, 'Unknown tool: ' + domain
    with push_config(c, project=project):
        app = project.app_instance(mount_point[0])
        if not app:
            raise AddressException, 'Unknown tool: ' + domain
    return userpart, project, app


def parse_message(data):
    # Parse the email to its constituent parts
    parser = email.feedparser.FeedParser()
    parser.feed(data)
    msg = parser.close()
    # Extract relevant data
    result = {}
    result['multipart'] = multipart = msg.is_multipart()
    result['headers'] = dict(msg)
    result['message_id'] = _parse_message_id(msg.get('Message-ID'))
    result['in_reply_to'] = _parse_message_id(msg.get('In-Reply-To'))
    result['references'] = _parse_message_id(msg.get('References'))
    if result['message_id'] == []:
        result['message_id'] = gen_message_id()
    else:
        result['message_id'] = result['message_id'][0]
    if multipart:
        result['parts'] = []
        for part in msg.walk():
            dpart = dict(
                headers=dict(part),
                message_id=result['message_id'],
                in_reply_to=result['in_reply_to'],
                references=result['references'],
                content_type=part.get_content_type(),
                filename=part.get_filename(None),
                payload=part.get_payload(decode=True))
            charset = part.get_content_charset()
            if charset:
                dpart['payload'] = dpart['payload'].decode(charset)
            result['parts'].append(dpart)
    else:
        result['payload'] = msg.get_payload(decode=True)
        charset = msg.get_content_charset()
        if charset:
            result['payload'] = result['payload'].decode(charset)
    return result

def identify_sender(peer, email_address, headers, msg):
    from vulcanforge.auth.model import EmailAddress, User
    # Dumb ID -- just look for email address claimed by a particular user
    email = EmailAddress.canonical(email_address)
    addr = EmailAddress.by_address(email)
    if addr and addr.claimed_by_user_id:
        return addr.claimed_by_user()
    email = EmailAddress.canonical(headers.get('From', ''))
    addr = EmailAddress.by_address(email)
    if addr and addr.claimed_by_user_id:
        return addr.claimed_by_user()
    return User.anonymous()

def encode_email_part(content, content_type):
    try:
        return MIMEText(
            content.encode('iso-8859-1'), content_type, 'iso-8859-1')
    except:
        return MIMEText(content.encode('utf-8'), content_type, 'utf-8')

def make_multipart_message(*parts):
    msg = MIMEMultipart('related')
    msg.preamble = 'This is a multi-part message in MIME format.'
    alt = MIMEMultipart('alternative')
    msg.attach(alt)
    for part in parts:
        alt.attach(part)
    return msg

def _parse_message_id(msgid):
    if msgid is None: return []
    return [ mo.group(1)
             for mo in RE_MESSAGE_ID.finditer(msgid) ]

def _parse_smtp_addr(addr):
    addr = str(addr)
    addrs = _parse_message_id(addr)
    if addrs and addrs[0]: return addrs[0]
    if '@' in addr: return addr
    # TODO: forgemail reference follows
    return 'noreply@in.vulcanforge.org'

def isvalid(addr):
    """
    return True if addr is a (possibly) valid email address, false
    otherwise

    """
    try:
        EMAIL_VALIDATOR.to_python(addr, None)
        return True
    except fev.Invalid:
        return False
    except:
        LOG.exception("Error converting {} to email".format(addr))
        return False


class SMTPClient(object):

    def __init__(self):
        self._client = None

    def sendmail(self, addrs, addrfrom, reply_to, subject, message_id,
                 in_reply_to, message):
        if not addrs:
            return
        charset = message.get_charset()
        if charset is None:
            charset = 'iso-8859-1'
        message['To'] = Header(reply_to, charset)
        message['From'] = Header(addrfrom, charset)
        message['Reply-To'] = Header(reply_to, charset)
        message['Subject'] = Header(subject, charset)
        message['Message-ID'] = Header('<' + message_id + '>', charset)
        if in_reply_to:
            if isinstance(in_reply_to, basestring):
                in_reply_to = [ in_reply_to ]
            in_reply_to = ','.join(('<' + irt + '>') for irt in in_reply_to)
            message['In-Reply-To'] = Header(in_reply_to, charset)
        content = message.as_string()
        smtp_addrs = map(_parse_smtp_addr, addrs)
        smtp_addrs = [ a for a in smtp_addrs if isvalid(a) ]
        if not smtp_addrs:
            LOG.warning('No valid addrs in %s, so not sending mail',
                map(unicode, addrs))
            return
        self._connect()
        r = self._client.sendmail(config.return_path, smtp_addrs, content)
        self._client.quit()
        return r

    def _connect(self):
        if asbool(tg.config.get('smtp_ssl', False)):
            smtp_client = smtplib.SMTP_SSL(
                tg.config.get('smtp_server', 'localhost'),
                asint(tg.config.get('smtp_port', 25)))
        else:
            smtp_client = smtplib.SMTP(
                tg.config.get('smtp_server', 'localhost'),
                asint(tg.config.get('smtp_port', 465)))
        if tg.config.get('smtp_user', None):
            smtp_client.login(tg.config['smtp_user'], tg.config['smtp_password'])
        if asbool(tg.config.get('smtp_tls', False)):
            smtp_client.starttls()
        self._client = smtp_client
