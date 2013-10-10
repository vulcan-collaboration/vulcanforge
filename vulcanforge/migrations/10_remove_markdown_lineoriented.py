import re
from ming.odm.odmsession import ThreadLocalODMSession
from vulcanforge.migration.base import BaseMigration
from vulcanforge.tools.tickets.model import Ticket
from vulcanforge.tools.wiki.model import Page


class RemoveMarkdownLineOrientatedProcessor(BaseMigration):
    """WARNING: this migration is NOT idempotent. DO NOT RUN TWICE"""

    def _convert_markdown(self, content):
        game_on = True
        split_content = content.replace('\r\n', '\n').split('\n')
        new_split = []
        max_i = len(split_content) - 1
        for i, line in enumerate(split_content):
            if line.startswith('~~~~'):
                game_on = not game_on
            new_split.append(line)
            if game_on and not line.startswith('    ') and \
                    not line.lstrip().startswith('- ') and line:
                if i != max_i and split_content[i + 1]:  # not double break
                    new_split.append('')

        return '\r\n'.join(new_split)

    def run(self):
        # only runs on wiki pages and tickets
        for wiki_page in Page.query.find({"deleted": False}):
            wiki_page.text = self._convert_markdown(wiki_page.text)

        ThreadLocalODMSession.flush_all()
        self.close_sessions()

        for ticket in Ticket.query.find():
            ticket.description = self._convert_markdown(ticket.description)

        ThreadLocalODMSession.flush_all()
