import logging

from ming.odm import Mapper
from pylons import app_globals as g

from vulcanforge.virusscan.model import S3VirusScannableMixin
from . import base

LOG = logging.getLogger(__name__)


class ScanFiles(base.Command):
    min_args = 1
    max_args = 1
    usage = '<ini file>'
    summary = 'Scan unscanned files'
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()

        for m in Mapper.all_mappers():
            if issubclass(m.mapped_class, S3VirusScannableMixin):
                instances = m.mapped_class.query.find({
                    '$and': [
                        {'$or': [
                            {'virus_scan_status': {'$exists': False}},
                            {'virus_scan_status': 'unscanned'}
                        ]},
                        {'$or': [
                            {'deleted': {'$exists': False}},
                            {'deleted': False}
                        ]}
                    ]
                })
                for instance in instances:
                    instance.scan_for_virus.post(
                        taskd_priority=g.clamav_task_priority)