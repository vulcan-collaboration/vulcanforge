from datetime import datetime
import re

from pylons import app_globals as g

DEFAULT_LIMIT = 10
STATIC_RESOURCE_REGEX = re.compile("/nf/[0-9]+?/_ew_/")
EXCHANGE_RESOURCE_REGEX = \
    re.compile('("exchange":.*?"icon_url": ")(images)')


def translate_exchange(mo):
    url_base = g.resource_manager.url_base
    return mo.group(1) + url_base + mo.group(2)


def translate_uris(results):
    url_base = g.resource_manager.url_base
    for doc in results.docs:
        json_s = doc['json_s']
        json_s = STATIC_RESOURCE_REGEX.sub(url_base, json_s)
        json_s = EXCHANGE_RESOURCE_REGEX.sub(translate_exchange, json_s)
        doc['json_s'] = json_s
    return results


def get_isodate_from_arg(date=None):
    date = date.rstrip('Z')
    try:
        return datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f").isoformat()
    except (ValueError, TypeError):
        pass
    try:
        return datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f").isoformat()
    except (ValueError, TypeError):
        pass
    return datetime.utcnow().isoformat()


def get_notifications(user, project=None, from_dt=None, to_dt=None, **kwargs):
    """query Solr for user notifications, returning results"""

    if project:
        app_config_ids = [str(x._id) for x in project.app_configs]
        exchange_uris = []
    else:
        activity_feed_state = user.state_preferences.get('activity_feed', {})
        app_config_state = activity_feed_state.get('app_config_state', {})
        app_config_ids = [str(k) for k, v in app_config_state.items() if v]
        exchange_state = activity_feed_state.get("exchange_state", {})
        exchange_uris = [k for k, v in exchange_state.items() if v]

    # get query based on filters
    q_list = []
    ac_query, xcng_query = None, None
    if len(app_config_ids):
        ac_query = "app_config_id_s:({})".format(
            ' OR '.join(app_config_ids))
    if len(exchange_uris):
        xcng_query = 'exchange_uri_s:({})'.format(
            ' OR '.join(exchange_uris))
    if ac_query and xcng_query:
        filter_query = '({} OR {})'.format(ac_query, xcng_query)
    elif ac_query:
        filter_query = ac_query
    elif xcng_query:
        filter_query = xcng_query
    else:  # no apps or exchanges engaged
        return '{"notifications":[]}'
    q_list.append(filter_query)

    # incorporate timestamp
    limit = kwargs.get('limit', DEFAULT_LIMIT)
    if from_dt or to_dt:
        drange_tmpl = "pubdate_dt:[{} TO {}]"
        param_specs = (from_dt, to_dt)
        drange_specs = []
        for p in param_specs:
            spec = "*"
            if p:
                iso = get_isodate_from_arg(p)
                spec = "{0}Z".format(iso.replace(':', '\:'))
            drange_specs.append(spec)
        q_list.append(drange_tmpl.format(*drange_specs))

    # permissions and query metadata
    read_roles = ' OR '.join(g.security.get_user_read_roles(user))
    solr_params = {
        'q': ' AND '.join(q_list),
        'fq': [
            'type_s:Notification',
            'read_roles:({})'.format(read_roles),
        ],
        'start': 0,
        'sort': 'pubdate_dt desc',
        'rows': limit,
    }
    # query solr
    results = g.solr.search(**solr_params)
    return translate_uris(results)


def get_user_notifications(user, auth_user, from_dt=None, to_dt=None, **kwargs):
    """return user-specific notifications"""
    q_list = ["author_id_s:" + str(user._id)]
    # incorporate timestamp
    limit = kwargs.get('limit', DEFAULT_LIMIT)
    if from_dt or to_dt:
        drange_tmpl = "pubdate_dt:[{} TO {}]"
        param_specs = (from_dt, to_dt)
        drange_specs = []
        for p in param_specs:
            spec = "*"
            if p:
                iso = get_isodate_from_arg(p)
                spec = "{0}Z".format(iso.replace(':', '\:'))
            drange_specs.append(spec)
        q_list.append(drange_tmpl.format(*drange_specs))

    read_roles = ' OR '.join(g.security.get_user_read_roles(auth_user))
    solr_params = {
        'q': ' AND '.join(q_list),
        'fq': [
            'type_s:Notification',
            'read_roles:({})'.format(read_roles),
        ],
        'start': 0,
        'sort': 'pubdate_dt desc',
        'rows': limit,
    }
    # query solr
    results = g.solr.search(**solr_params)
    return translate_uris(results)
