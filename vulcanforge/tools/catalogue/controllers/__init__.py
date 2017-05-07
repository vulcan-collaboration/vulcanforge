import logging

from datetime import datetime

LOG = logging.getLogger(__name__)

SOLR_DATE_FMT = '%Y-%m-%dT%H:%M:%S.%fZ'
SOLR_DATE_FMT_2 = '%Y-%m-%dT%H:%M:%SZ'


def _parse_solr_date(date_str):
    try:
        return datetime.strptime(date_str, SOLR_DATE_FMT)
    except ValueError:
        return datetime.strptime(date_str, SOLR_DATE_FMT_2)
