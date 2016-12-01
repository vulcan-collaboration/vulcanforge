from logging import getLogger

from pylons import tmpl_context as c, app_globals as g
import pysolr

from vulcanforge.common.util.exception import exceptionless


LOG = getLogger(__name__)


def solarize(obj):
    if obj is None:
        return None
    doc = obj.index()
    return doc


def dictify_facet_list(facet_list):
    list_iter = iter(facet_list)
    return dict(zip(list_iter, list_iter))


class SolrSearch(object):

    dynamic_postfixes = [
        '_i',
        '_s',
        '_l',
        '_t',
        '_b',
        '_f',
        '_d',
        '_dt',
        '_s_mv'
    ]

    def __init__(self, solr):
        self.solr = solr

    @exceptionless(None, log=LOG)
    def __call__(self, q, **kw):
        return self.solr.search(q, **kw)

    def search_artifact(self, atype, q, history=False, rows=10, fq_dict=None,
                        **kw):
        """Performs SOLR search.

        Raises ValueError if SOLR returns an error.

        """
        # first, grab an artifact and get the fields that it indexes
        a = atype.query.find().first()
        if a is None:
            return  # if there are no instance of atype, we won't find anything
        fields = a.index()
        # Now, we'll translate all the fld:
        q = atype.translate_query(q, fields)
        if fq_dict is None:
            fq_dict = dict()
        fq1 = dict(
            type_s=fields['type_s'],
            project_id_s=c.project._id,
            mount_point_s=c.app.config.options.mount_point
        )
        if not history:
            fq1['is_history_b'] = 'False'
        fq1.update(fq_dict)
        fq = ['{}:({})'.format(k, v) for k, v in fq1.iteritems()]
        return self(q, fq=fq, rows=rows, **kw)
