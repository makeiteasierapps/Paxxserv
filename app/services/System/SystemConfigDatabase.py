from fastapi import HTTPException
from typing import List, Dict, Any, Optional
from pymongo.results import UpdateResult

class SystemConfigDatabase:
    def __init__(self, mongo_client):
        self.db = mongo_client.db
        self.config_collection = self.db.system_config
        self.users_collection = self.db.users

    async def check_if_user_authorized(self, uid: str) -> bool:
        """Check if user has system access permissions"""
        user = await self.users_collection.find_one({"_id": uid})
        if not user or not user.get("is_admin"):
            raise HTTPException(status_code=403, detail="User not authorized for system operations")
        return True

    async def update_file_commands(self, file_path: str, restart_command: str = None, test_command: str = None) -> UpdateResult:
        """Update restart and test commands for a specific config file"""
        # Build the update object dynamically based on provided values
        update_fields = {}
        if restart_command is not None:
            update_fields["config_files.$[elem].restart_command"] = restart_command
        if test_command is not None:
            update_fields["config_files.$[elem].test_command"] = test_command
        
        return await self.config_collection.update_one(
            {},
            {"$set": update_fields},
            array_filters=[{"elem.path": file_path}]
        )

    async def update_or_insert_file(self, file_path: str, content: str, category: str) -> UpdateResult:
        """Update or insert a config file in the database"""
        return await self.config_collection.update_one(
            {"config_files.path": file_path},
            {
                "$set": {
                    "config_files.$.content": content,
                    "config_files.$.category": category
                }
            },
            upsert=True
        )

    async def update_combined_files(self, combined_files: List[Dict[str, Any]]) -> UpdateResult:
        """Update combined files in the database"""
        return await self.config_collection.update_one(
            {},
            {"$set": {"combined_files": combined_files}},
            upsert=True
        )

    async def update_config_categories(self, categories: List[Dict[str, Any]]) -> UpdateResult:
        """Update config categories in the database"""
        return await self.config_collection.update_one(
            {},
            {"$set": {"config_categories": categories}},
            upsert=True
        )

    async def get_files_by_category(self, category: str) -> Optional[Dict[str, Any]]:
        """Get files by category"""
        return await self.config_collection.find_one(
            {"config_files.category": category}
        )

    async def get_index_path(self) -> Optional[str]:
        """Get index path from config"""
        try:
            config = await self.config_collection.find_one({})
            return config.get('index_path', None) if config else None
        except Exception as e:
            raise Exception(f"Error getting index path: {str(e)}")

    async def add_index_path(self, index_path: str) -> None:
        """Add or update index path"""
        try:
            await self.config_collection.update_one(
                {},
                {"$set": {"index_path": index_path}},
                upsert=True
            )
        except Exception as e:
            raise Exception(f"Error adding index path: {str(e)}")