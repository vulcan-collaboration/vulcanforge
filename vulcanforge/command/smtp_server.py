import logging
import smtpd

import tg
from paste.script import command
from paste.deploy.converters import asint
import asyncore
from vulcanforge.notification.tasks import route_email

from . import base


class SMTPServerCommand(base.Command):
    min_args = 1
    max_args = 1
    usage = '<ini file>'
    summary = 'Handle incoming emails, routing them to RabbitMQ'
    parser = command.Command.standard_parser(verbose=True)
    parser.add_option('-c', '--context', dest='context',
                      help=('The context of the message (path to the project'
                            ' and/or tool'))

    def command(self):
        self.basic_setup()
        MailServer((tg.config.get('forgemail.host', '0.0.0.0'),
                    asint(tg.config.get('forgemail.port', 8825))),
                   None)
        asyncore.loop()


class MailServer(smtpd.SMTPServer):

    def __init__(self, localaddr, remoteaddr, logger=None):
        smtpd.SMTPServer.__init__(self, localaddr, remoteaddr)
        self.logger = logger or logging.getLogger(__name__)

    def log(self, message):
        self.logger.info(message)

    def log_info(self, message, type='info'):
        if type == 'error':
            log_function = self.logger.error
        elif type == 'warning':
            log_function = self.logger.warn
        else:
            log_function = self.logger.info
        log_function(message)

    def process_message(self, peer, mailfrom, rcpttos, data):
        self.logger.info('Msg Received from %s for %s', mailfrom, rcpttos)
        self.logger.info(' (%d bytes)', len(data))
        route_email(peer=peer, mailfrom=mailfrom, rcpttos=rcpttos, data=data)
        self.logger.info('Msg passed along')
