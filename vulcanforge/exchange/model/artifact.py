import logging

import bson
from ming import schema
from ming.odm import FieldProperty

from vulcanforge.artifact.model import Artifact
from vulcanforge.exchange.model import ExchangeNode

LOG = logging.getLogger(__name__)


class ExchangeableArtifact(Artifact):
    """
    Artifact with methods and properties needed for interaction with the
    Exchange.

    Note that this is often used as a mixin, so it is best to avoid overriding
    parent behavior.

    """
    import_source_id = FieldProperty(schema.ObjectId, if_missing=None)

    @property
    def import_source(self):
        if self.import_source_id:
            return self.__class__.query.get(
                _id=bson.ObjectId(self.import_source_id))

    def exchange_index_fields(self):
        return {"labels_t": ' '.join(self.labels)}

    def get_direct_dependencies(self):
        return []

    def get_dependencies(self):
        dependencies = []
        for dependency in self.get_direct_dependencies():
            dependencies.append(dependency)
            if hasattr(dependency, 'get_dependencies'):
                dependencies.extend(dependency.get_dependencies())
        return dependencies

    def delete(self):
        # Find all the nodes and delete them
        exchange_nodes = ExchangeNode.find_from_artifact(self).all()
        for exchange_node in exchange_nodes:
            exchange_node.unpublish()

        super(ExchangeableArtifact, self).delete()

    def publish_hook(self, **kwargs):
        pass

    def unpublish_hook(self, **kwargs):
        pass

    def view_hook(self, **kwargs):
        pass
