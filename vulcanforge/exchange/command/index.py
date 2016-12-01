import logging

from pylons import app_globals as g

from vulcanforge.command import Command
from vulcanforge.exchange.model import ExchangeNode
from vulcanforge.artifact.model import ArtifactReference
from vulcanforge.artifact.tasks import add_artifacts
from vulcanforge.common.util.model import chunked_find

LOG = logging.getLogger(__name__)


class ReindexExchangeCommand(Command):
    min_args = 0
    max_args = 1
    usage = '<ini file>'
    summary = 'Reindex exchange nodes'
    parser = Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()

        LOG.info('Reindexing all exchange nodes')
        g.solr.delete(q='type_s:"Exchange Node"')
        for nodes in chunked_find(ExchangeNode, {}):
            for node in nodes:
                # Temporary measure
                try:
                    # Update the index_fields
                    node.update_index_fields()
                    node.flush_self()
                    ref_ids = [(ArtifactReference.from_artifact(node))._id]
                    if ref_ids:
                        add_artifacts.post(ref_ids)
                except:
                    pass

        LOG.info('Reindex done')