from vulcanforge.auth.model import User
from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.migration.base import BaseMigration
from vulcanforge.project.model import ProjectRole, Project


class AddUserHasProject(BaseMigration):
    def run(self):
        count = 0
        db, user_coll = pymongo_db_collection(User)
        db, role_coll = pymongo_db_collection(ProjectRole)
        db, proj_coll = pymongo_db_collection(Project)
        nbhd_proj_ids = [d["_id"] for d in
                         proj_coll.find({"shortname": "__init__"})]
        user_query = {
            "has_project": {"$ne": True},
            "username": {"$nin": ["*anonymous", "root", "admin"]}
        }
        for user_doc in user_coll.find(user_query):
            user_role_ids = []
            ur_query = {
                "user_id": user_doc["_id"],
                "project_id": {"$nin": nbhd_proj_ids}
            }
            for user_role in role_coll.find(ur_query):
                user_role_ids.extend(user_role["roles"])
            role = role_coll.find_one({
                "_id": {"$in": user_role_ids},
                "name": {"$ne": None},
                "project_id": {"$nin": nbhd_proj_ids}  # just to make sure
            })
            if role:
                user_doc["has_project"] = True
                user_coll.save(user_doc)
                count += 1
        self.write_output(
            "Added has_project to {} users with projects".format(count))
