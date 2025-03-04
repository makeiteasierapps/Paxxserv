from fastapi import HTTPException
from app.services.System.SystemStateManager import SystemStateManager

class SystemService:
    def __init__(self, system_manager: SystemStateManager, uid: str):
        self.system_manager = system_manager
        self.uid = uid

    async def initialize(self):
        """Initialize the service and verify user"""
        await self._verify_user()
        return self

    async def _verify_user(self):
        """Verify user has access to system operations"""
        try:
            await self.system_manager.config_db.check_if_user_authorized(self.uid)
        except HTTPException as e:
            self.system_manager.logger.error(f"User {self.uid} is not authorized to access this resource")
            raise e

    async def update_file_commands(self, file_obj: dict):
        """Update the restart and test commands for a specific file"""
        await self.system_manager.update_file_commands(self.uid, file_obj)

    async def create_config_file(self, file_obj: dict):
        """Create a configuration file"""
        return await self.system_manager.create_config_file(file_obj['path'], file_obj['content'], file_obj['category'])

    async def write_config_file(self, file_obj: dict):
        """Write configuration file using file object"""
        return await self.system_manager.update_config_file(file_obj, self.uid)

    async def read_config_file(self, filename: str):
        """Read content from a configuration file"""
        return await self.system_manager.read_config_file(filename)

    async def check_if_config_file_exists(self, filename: str):
        """Check if a configuration file exists"""
        return await self.system_manager.check_if_config_file_exists_on_server(filename)

    def get_systemd_services(self):
        """Get list of SystemD services"""
        return self.system_manager.get_systemd_services()

    def check_systemd_services(self):
        """Check status of SystemD services"""
        return self.system_manager.check_systemd_services()

    async def combine_config_files_by_category(self):
        """Combine and update config files by category"""
        return await self.system_manager.combine_config_files_by_category()
    
    async def get_config_categories(self):
        """Get all configuration categories"""
        return await self.system_manager.get_config_categories()

    async def get_config_files_by_category(self, category: str):
        """Get config files by category"""
        return await self.system_manager.get_config_files_by_category(category)

    def get_config_files(self):
        """Get all configuration files"""
        return self.system_manager.get_config_files_as_list()
