class SystemConfigDatabase:
    def __init__(self, db, uid):
        self.db = db
        self.uid = uid

    def fetch_user_config(self):
        return self.db.system_config.find_one({"uid": self.uid}) or {}

    def update_combined_files(self, combined_files):
        self.db.system_config.update_one(
            {"uid": self.uid},
            {"$set": {"combined_files": combined_files}},
            upsert=True
        )

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