import pymongo
from vulcanforge.auth.model import User
from vulcanforge.common.model.globals import ForgeGlobals
from vulcanforge.migration.base import BaseMigration


class AddUserOSId(BaseMigration):

    def run(self):
        if not ForgeGlobals.query.get():
            counter = len([u for u in User.query.find() if u.is_real_user()])
            ForgeGlobals(user_counter=counter + 1)

        cur_max_user = User.query.find({
            "os_id": {"$exists": 1, "$ne": None}}).sort("os_id", pymongo.DESCENDING).first()
        if cur_max_user:
            cur_id = cur_max_user.os_id + 1
        else:
            cur_id = 1
        for user in User.query.find({"os_id": {"$exists": 0}}).sort("_id"):
            if user.is_real_user():
                user.os_id = cur_id
                cur_id += 1
