import logging

from ming.odm import state

LOG = logging.getLogger(__name__)


class ArtifactImporter(object):

    def __init__(self, artifact):
        super(ArtifactImporter, self).__init__()
        self.artifact = artifact
        self.new_instance = None

    def do_import(self, **kwargs):
        properties = self._get_properties_to_import()
        properties.update(kwargs)
        properties['import_source_id'] = self.artifact._id
        self.pre_import(properties)
        self.new_instance = self.artifact.__class__(**properties)
        self.post_import()
        return self.new_instance

    @property
    def excluded_properties(self):
        return [
            '_id',
            'mod_date',
            'acl',
            'version',
            'last_updated',
            'import_source_id',
            'preview_url',
            'alt_resources',
            'app_config_id'
        ]

    def _get_properties_to_import(self):
        properties = {}
        excluded = self.excluded_properties
        for name, value in state(self.artifact).clone().items():
            if name not in excluded:
                properties[name] = value
        return properties

    def pre_import(self, properties):
        """Hook to modify import properties"""
        pass

    def post_import(self):
        if callable(getattr(self.new_instance, 'commit', None)):
            self.new_instance.commit()
