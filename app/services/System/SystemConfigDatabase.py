from fastapi import HTTPException

class SystemConfigDatabase:
    def __init__(self, db, uid):
        self.db = db
        self.uid = uid

    def check_if_user_authorized(self):
        user = self.db.users.find_one({"_id": self.uid})
        if not user or not user.get('is_admin', False):
            raise HTTPException(status_code=403, detail="Unauthorized access")

    def fetch_user_config(self):
        return self.db.system_config.find_one({"uid": self.uid}) or {}

    def update_combined_files(self, combined_files):
        self.db.system_config.update_one(
            {"uid": self.uid},
            {"$set": {"combined_files": combined_files}},
            upsert=True
        )
    def get_files_by_category(self, category):
        print(category)
        return self.db.system_config.find_one({"uid": self.uid, "config_files.category": category})
    
    def update_config_categories(self, config_categories):
        self.db.system_config.update_one(
            {"uid": self.uid},
            {"$set": {"config_categories": config_categories}}
        )

    def update_or_insert_file(self, file_path, content, category):
        update_result = self.db.system_config.update_one(
            {"uid": self.uid, "config_files.path": file_path},
            {
                "$set": {
                    "config_files.$.content": content,
                    "config_files.$.category": category
                }
            }
        )

        if update_result.matched_count == 0:
            self.db.system_config.update_one(
                {"uid": self.uid},
                {"$push": {"config_files": {"path": file_path, "content": content, "category": category}}},
                upsert=True
            )

        return update_result
    
    def get_index_path(self):
        try:
            config = self.db.system_config.find_one({'uid': self.uid})
            return config.get('index_path', None)
        except Exception as e:
            raise Exception(f"Error getting index path: {str(e)}")

    def add_index_path(self, index_path):
        try:
            self.db.system_config.update_one({'uid': self.uid}, {'$set': {'index_path': index_path}})
        except Exception as e:
            raise Exception(f"Error adding index path: {str(e)}")