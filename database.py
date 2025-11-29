from config import Config
import motor.motor_asyncio
from pymongo import MongoClient


async def mongodb_version():
    x = MongoClient(Config.DATABASE_URI)
    return x.server_info()["version"]


class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.bot = self.db.bots
        self.col = self.db.users
        self.nfy = self.db.notify
        self.chl = self.db.channels

    # ---------- USER ----------
    def new_user(self, id, name):
        return {
            "id": id,
            "name": name,
            "ban_status": {
                "is_banned": False,
                "ban_reason": ""
            }
        }

    async def add_user(self, id, name):
        await self.col.insert_one(self.new_user(id, name))

    async def is_user_exist(self, id):
        return bool(await self.col.find_one({"id": int(id)}))

    async def total_users_bots_count(self):
        return (
            await self.col.count_documents({}),
            await self.bot.count_documents({})
        )

    async def total_channels(self):
        return await self.chl.count_documents({})

    async def remove_ban(self, id):
        await self.col.update_one(
            {"id": id},
            {"$set": {"ban_status": {"is_banned": False, "ban_reason": ""}}}
        )

    async def ban_user(self, user_id, ban_reason="No Reason"):
        await self.col.update_one(
            {"id": user_id},
            {"$set": {"ban_status": {"is_banned": True, "ban_reason": ban_reason}}}
        )

    async def get_ban_status(self, id):
        default = {"is_banned": False, "ban_reason": ""}
        user = await self.col.find_one({"id": int(id)})
        return user.get("ban_status", default) if user else default

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({"id": int(user_id)})

    async def get_banned(self):
        users = self.col.find({"ban_status.is_banned": True})
        return [u["id"] async for u in users]

    # ---------- CONFIGS ----------
    async def update_configs(self, id, configs):
        await self.col.update_one({"id": int(id)}, {"$set": {"configs": configs}})

    async def get_configs(self, id):
        default = {
            "caption": None,
            "duplicate": True,
            "forward_tag": False,
            "file_size": 0,
            "size_limit": None,
            "extension": None,
            "keywords": None,
            "protect": None,
            "button": None,
            "db_uri": None,
            "filters": {
                "poll": True,
                "text": True,
                "audio": True,
                "voice": True,
                "video": True,
                "photo": True,
                "document": True,
                "animation": True,
                "sticker": True
            }
        }

        user = await self.col.find_one({"id": int(id)})
        return user.get("configs", default) if user else default

    async def get_filters(self, user_id):
        filters = (await self.get_configs(user_id))["filters"]
        return [k for k, v in filters.items() if not v]

    # ---------- BOT ----------
    async def add_bot(self, datas):
        if not await self.is_bot_exist(datas["user_id"]):
            await self.bot.insert_one(datas)

    async def remove_bot(self, user_id):
        await self.bot.delete_many({"user_id": int(user_id)})

    async def get_bot(self, user_id):
        return await self.bot.find_one({"user_id": int(user_id)})

    async def is_bot_exist(self, user_id):
        return bool(await self.bot.find_one({"user_id": int(user_id)}))

    # ---------- CHANNELS ----------
    async def in_channel(self, user_id, chat_id):
        return bool(await self.chl.find_one({
            "user_id": int(user_id), 
            "chat_id": int(chat_id)
        }))

    async def add_channel(self, user_id, chat_id, title, username):
        if await self.in_channel(user_id, chat_id):
            return False

        return await self.chl.insert_one({
            "user_id": int(user_id),
            "chat_id": int(chat_id),
            "title": title,
            "username": username
        })

    async def remove_channel(self, user_id, chat_id):
        if not await self.in_channel(user_id, chat_id):
            return False

        return await self.chl.delete_many({
            "user_id": int(user_id),
            "chat_id": int(chat_id)
        })

    async def get_channel_details(self, user_id, chat_id):
        return await self.chl.find_one({
            "user_id": int(user_id),
            "chat_id": int(chat_id)
        })

    async def get_user_channels(self, user_id):
        cursor = self.chl.find({"user_id": int(user_id)})
        return [c async for c in cursor]

    # ---------- FORWARD NOTIFY ----------
    async def add_frwd(self, user_id):
        return await self.nfy.insert_one({"user_id": int(user_id)})

    async def rmve_frwd(self, user_id=0, all=False):
        data = {} if all else {"user_id": int(user_id)}
        return await self.nfy.delete_many(data)

    async def get_all_frwd(self):
        return self.nfy.find({})


db = Database(Config.DATABASE_URI, Config.DATABASE_NAME)
