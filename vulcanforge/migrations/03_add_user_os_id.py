import pymongo
from vulcanforge.auth.model import User
from vulcanforge.migration.base import BaseMigration


class AddUserOSId(BaseMigration):

    def run(self):
        cur_max_user = User.query.find({
            "os_id": {"$exists": 1}}).sort("os_id", pymongo.DESCENDING).first()
        if cur_max_user:
            cur_id = cur_max_user.os_id + 1
        else:
            cur_id = 1
        for user in User.query.find({"os_id": {"$exists": 0}}).sort("_id"):
            user.os_id = cur_id
            cur_id += 1
