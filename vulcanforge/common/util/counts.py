from bson import ObjectId
from bson.code import Code
from datetime import datetime

from ming.odm.odmsession import ThreadLocalODMSession
from pylons import app_globals as g, tmpl_context as c

from vulcanforge.auth.model import AppVisit, ToolsInfo
from vulcanforge.exchange.model import ExchangeVisit
from vulcanforge.exchange.solr import exchange_access_filter
from vulcanforge.project.model import Project, AppConfig


def get_exchange_counts(user, xchng_name):
    """returns counts of user's projects sharing in an exchange"""
    exchange = g.exchange_manager.get_exchange_by_uri(xchng_name)
    exchange_visit = ExchangeVisit.query.get(
        user_id=user._id,
        exchange_uri=exchange.config["uri"]
    )
    project_ids = set(
        str(role.project_id) for role in user.get_roles() if role.name)

    ##############
    # Nodes shared by
    ##############

    # assemble the query
    query_l = []
    project_id_s = ' OR '.join(map(str, [p._id for p in user.my_projects()]))

    project_filter = "project_id_s:({})".format(project_id_s)
    query_l.extend([
        'NOT deleted_b:true',  # Make sure deleted items are not listed
        'type_s:"{}"'.format(exchange.config["node"].type_s),
        'exchange_uri_s:"{}"'.format(exchange.config["uri"]),
        exchange_access_filter(),
        project_filter
    ])
    query = ' AND '.join(query_l)

    # run the search
    params = {
        "q": query,
        "facet": "on",
        "facet.field": "tool_name_s",
        "rows": 0
    }
    nodes_shared_by = {}
    result = g.search(**params)
    if result is not None:
        facet_iter = iter(result.facets['facet_fields']['tool_name_s'])
        for tool_name_s, count in zip(facet_iter, facet_iter):
            if count:
                nodes_shared_by[tool_name_s] = {'new': count, 'all': count}

    if exchange_visit is not None and \
            isinstance(exchange_visit.last_visit, datetime):

        query_l.append('mod_date_dt:[{}Z TO *]'.format(
            exchange_visit.last_visit.isoformat()))
        query = ' AND '.join(query_l)
        params = {
            "q": query,
            "facet": "on",
            "facet.field": "tool_name_s",
            "rows": 0
        }
        result = g.search(**params)
        if result is not None:
            facet_iter = iter(result.facets['facet_fields']['tool_name_s'])
            facet_dict = dict(zip(facet_iter, facet_iter))
            for tool_name in nodes_shared_by.keys():
                nodes_shared_by[tool_name]['new'] = facet_dict.get(tool_name, 0)

    ##############
    # Nodes shared by
    ##############

    query_l = []
    project_filter = "-project_id_s:({})".format(project_id_s)
    query_l.extend([
        'NOT deleted_b:true',  # Make sure deleted items are not listed
        'type_s:"{}"'.format(exchange.config["node"].type_s),
        'exchange_uri_s:"{}"'.format(exchange.config["uri"]),
        exchange_access_filter(),
        project_filter
    ])
    query = ' AND '.join(query_l)

    params = {
        "q": query,
        "facet": "on",
        "facet.field": "tool_name_s",
        "rows": 0
    }
    nodes_shared_with = {}
    result = g.search(**params)
    if result is not None:
        facet_iter = iter(result.facets['facet_fields']['tool_name_s'])
        for tool_name_s, count in zip(facet_iter, facet_iter):
            if count:
                nodes_shared_with[tool_name_s] = {'new': count, 'all': count}

    if exchange_visit is not None and \
            isinstance(exchange_visit.last_visit, datetime):

        query_l.append('mod_date_dt:[{}Z TO *]'.format(
            exchange_visit.last_visit.isoformat()))
        query = ' AND '.join(query_l)
        params = {
            "q": query,
            "facet": "on",
            "facet.field": "tool_name_s",
            "rows": 0
        }
        result = g.search(**params)
        if result is not None:
            facet_iter = iter(result.facets['facet_fields']['tool_name_s'])
            facet_dict = dict(zip(facet_iter, facet_iter))
            for tool_name in nodes_shared_with.keys():
                nodes_shared_with[tool_name]['new'] = facet_dict.get(tool_name, 0)

    return {
        'nodes_shared_by': nodes_shared_by,
        'nodes_shared_with': nodes_shared_with
    }


def get_artifact_counts(user, project_shortname=None, permission="read",
                        project_ids=None):
    """Returns tool information for user's projects, or a specific project"""
    tools = []
    av_query = {"user_id": user._id}
    if project_shortname:
        project = Project.by_shortname(project_shortname)
        ac_query = {"project_id": project._id}
        av_query["project_id"] = project._id
    elif project_ids:
        ac_query = {"project_id": {"$in": list(project_ids)}}
        av_query["project_id"] = {"$in": list(project_ids)}
    else:
        project_ids = set(
            role.project_id for role in user.get_roles() if role.name)
        ac_query = {"project_id": {"$in": list(project_ids)}}
        av_query["project_id"] = {"$in": list(project_ids)}

    app_visits = AppVisit.query.find(av_query).all()
    visit_times = {}
    for app_visit in app_visits:
        visit_times[app_visit.app_config_id] = app_visit.last_visit

    for ac in AppConfig.query.find(ac_query):
        if ac.has_access(permission, user):
            try:
                app = ac.instantiate()
                last_visit = visit_times.get(ac._id, None)
                artifact_counts = app.artifact_counts(since=last_visit)
                if last_visit is None:
                    artifact_counts['new'] = 0
                tools.append({
                    "url": ac.url(),
                    "id": str(ac._id),
                    "tool_name": ac.tool_name,
                    "mount_label": ac.options.mount_label,
                    "project_shortname": ac.project.shortname,
                    "project_name": ac.project.name,
                    "artifact_counts": artifact_counts,
                    "last_visited": visit_times.get(ac._id, None)
                })
            except:
                pass

    return {'tools': tools}


def get_time_references(time_range):
    try:
        t1, t2 = time_range
        if t1 and not t2:
            return {"_id": {"$gt": ObjectId.from_datetime(t1)}}
        if t2 and not t1:
            return {"_id": {"$lte": ObjectId.from_datetime(t2)}}
        if t1 and t2:
            return {"$and": [{"_id": {"$gt": ObjectId.from_datetime(t1)}},
                             {"_id": {"$lte": ObjectId.from_datetime(t2)}}]}
    except:
        pass
    return {}


def get_home_info(role_coll, app_configs, app_visits, tool_name, trefs=[]):
    my_app_configs = {k: v for k, v in app_configs.items()
                      if v.tool_name == tool_name}
    my_app_visits = {str(x.project_id): app_visits[str(x._id)]
                     for x in my_app_configs.values()}
    project_ids = {x.project_id: x for x in my_app_configs.values()}

    base_query = {"project_id": {"$in": project_ids.keys()},
                  "user_id": {"$ne": None},
                  "roles": {"$ne": []}}
    # time reference interval
    if trefs:
        base_query.update(get_time_references(trefs))
    reducer = Code("""
                    function(obj, gcounts) {
                        var visits = %s;
                        gcounts.all++;
                        var ac = obj.project_id.str;
                        if (obj._id > visits[ac]) {
                            gcounts.new++;
                        }
                    }
                    """ % my_app_visits)
    # perform query
    result = role_coll.group(key=["project_id"],
                             condition=base_query,
                             initial=dict(all=0, new=0),
                             reduce=reducer)
    # restructure
    retval = {x: dict(all=0, new=0) for x in my_app_configs}
    for item in result:
        ac_id = project_ids[item['project_id']]._id
        retval[ac_id] = {x: int(item[x]) for x in ('all', 'new')}
    return retval


def get_info(artifact_coll, app_configs, app_visits, tool_name,
             size_item, has_deleted=True, trefs=[]):
    """returns tool info for user's projects for tools by kind"""
    my_app_configs = {k: v for k, v in app_configs.items()
                      if v.tool_name == tool_name }
    my_app_visits = {k: v for k, v in app_visits.items()
                     if ObjectId(k) in my_app_configs}
    base_query = {"app_config_id": {"$in": my_app_configs.keys()}}
    if has_deleted:
        base_query["deleted"] = False
    # time reference interval
    if trefs:
        base_query.update(get_time_references(trefs))
    reducer = Code("""
                    function(obj, gcounts) {
                        var visits = %s;
                        gcounts.all++;
                        gcounts.total += obj.%s;
                        var ac = obj.app_config_id.str;
                        if (obj._id > visits[ac]) {
                            gcounts.new++;
                        }
                    }
                    """ % (my_app_visits, size_item))
    #perform query
    result = artifact_coll.group(key=["app_config_id"],
                                 condition=base_query,
                                 initial=dict(all=0, new=0, total=0),
                                 reduce=reducer)
    # restructure
    counts = ["all", "new"]
    if size_item:
        counts.append("total")
    retval = {x: {y: 0 for y in counts} for x in my_app_configs}
    for item in result:
        retval[item['app_config_id']] = {x: int(item[x]) for x in counts}
    return retval


def get_history_info(artifact_coll, app_configs, app_visits, tool_name,
                     trefs=[]):
    """returns tool info for user's projects for tools by kind"""
    my_app_configs = {k: v for k, v in app_configs.items()
                      if v.tool_name == tool_name }
    my_app_visits = {k: v for k, v in app_visits.items()
                     if ObjectId(k) in my_app_configs}
    base_query = {"app_config_id": {"$in": my_app_configs.keys()}}
    # time reference interval
    if trefs:
        base_query.update(get_time_references(trefs))
    reducer = Code("""
                    function(obj, gcounts) {
                        var visits = %s;
                        gcounts.all++;
                        var ac = obj.app_config_id.str;
                        if (obj._id > visits[ac]) {
                            gcounts.new++;
                        }
                    }
                    """ % my_app_visits)
    #perform query
    result = artifact_coll.group(key=["app_config_id", "artifact_id"],
                                 condition=base_query,
                                 initial=dict(all=0, new=0),
                                 reduce=reducer)
    # restructure
    retval = {x: dict(all=0, new=0) for x in my_app_configs}
    for item in result:
        ac_id = item['app_config_id']
        retval[ac_id]['all'] += 1
        if item['new']:
            retval[ac_id]['new'] += 1
    return retval

def get_tools_info(user, project_ids, permission="read", auth_user=None):
    timestamp = datetime.utcnow()
    auth_user = auth_user or user
    app_configs = AppConfig.query.find({"project_id": {"$in": project_ids}})
    cached_info = (ToolsInfo.query.get(user_id=user._id)
                   if user == auth_user else None)
    trefs = [cached_info.timestamp if cached_info else None, timestamp]
    authorized_apps = {x._id: x for x in app_configs
                       if x.has_access(permission, auth_user)}
    q = {"user_id": user._id,
         "app_config_id": {"$in": authorized_apps.keys()}}
    vc = AppVisit.query.find(q)
    app_visits = {x.app_config_id: x.last_visit for x in vc}
    visits = {str(x):
        ObjectId.from_datetime(app_visits.get(x, datetime.utcnow()))
        for x in authorized_apps.keys()
    }
    # collect tool information by tool kind
    results = {}
    tool_names = set([x.tool_name for x in authorized_apps.values()])
    for tool_name in list(tool_names):
        app = g.tool_manager.tools[tool_name.lower()]['app']
        cls_method = app.artifact_counts_by_kind
        results[tool_name] = cls_method(authorized_apps, visits, tool_name,
                                        trefs)
    info = {}
    for tool_name in results:
        for id in results[tool_name]:
            sid = str(id)
            if cached_info and sid in cached_info.info:
                item = cached_info.info[sid]
                app_visit = app_visits.get(id, None)
                if app_visit and app_visit > cached_info.timestamp:
                    item['new'] = results[tool_name][id]['new']
                else:
                    item['new'] += results[tool_name][id]['new']
                item['all'] += results[tool_name][id]['all']
            else:
                item = results[tool_name][id]
            info[sid] = dict(item)

    if cached_info:
        new_apps = {x: authorized_apps[x] for x in authorized_apps
                    if str(x) not in cached_info.info}
        new_tool_names = set([x.tool_name for x in new_apps.values()])
        trefs = [None, timestamp]
        new_results = {}
        for tool_name in list(new_tool_names):
            app = g.tool_manager.tools[tool_name.lower()]['app']
            cls_method = app.artifact_counts_by_kind
            new_results[tool_name] = cls_method(new_apps, visits, tool_name,
                                                trefs)
        for tool_name in new_results:
            for id in new_results[tool_name]:
                info[str(id)] = dict(new_results[tool_name][id])

    # cache result
    if user == auth_user:
        if not cached_info:
            cached_info = ToolsInfo()
            cached_info.user_id = user._id
        cached_info.timestamp = timestamp
        cached_info.info = info

    # prepare results
    tools = []
    for id, ac in authorized_apps.items():
        tools.append({
            "url": ac.url(),
            "id": str(id),
            "tool_name": ac.tool_name,
            "mount_label": ac.options.mount_label,
            "project_shortname": ac.project.shortname,
            "project_name": ac.project.name,
            "artifact_counts": dict(info[str(id)]),
            "last_visited": visits[str(id)].generation_time
        })
    return {'tools': tools}
