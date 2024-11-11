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

<<<<<<< HEAD
    async def write_config_file(self, file_obj: dict):
        """Write configuration file using file object"""
        return await self.system_manager.update_config_file(file_obj, self.uid)
=======
        # Iterate over config_files and combine contents by category
        for file in self.config_files:
            category = file['category']
            path = file['path']
            content = file['content']

            if category not in category_contents:
                category_contents[category] = ""

            category_contents[category] += f"{path}\n{content}\n\n"

        # Create combined_files collection
        combined_files = []
        for category, content in category_contents.items():
            token_count = token_counter(content)
            combined_files.append({
                "category": category,
                "content": content,
                "token_count": token_count
            })

        # Update the database
        self.config_db.update_combined_files(combined_files)
        return combined_files
    
    def add_new_config_category(self, category: str, key: str, validate_cmd: str, restart_cmd: str):
        if category not in self.config_categories:
            self.config_categories[category] = {
                'name': category,
                'key': key,
                'validate_cmd': validate_cmd,
                'restart_cmd': restart_cmd
            }
            self.config_db.update_config_categories(list(self.config_categories.values()))

    async def write_config_file(self, file_path: str, content: str, category: str):
        file_path = '/' + file_path.lstrip('/')
        ssh_client = self.ssh_manager.get_client() if self.is_dev_mode else None
        try:
            await self.config_file_manager.write_file(file_path, content, ssh_client)
            update_result = self.config_db.update_or_insert_file(file_path, content, category)
            self._update_in_memory_config(file_path, content, category)
            self.logger.info(f"Database update result: matched={update_result.matched_count}, modified={update_result.modified_count}")
            return await self._handle_service_validation(category)
        except Exception as e:
            self.logger.error(f"Error writing to file {file_path}: {str(e)}")
            raise HTTPException(status_code=500, detail="Error writing to configuration file")
        finally:
            if ssh_client:
                ssh_client.close()

    def _update_in_memory_config(self, file_path: str, content: str, category: str):
        existing_file = next((item for item in self.config_files if item['path'] == file_path), None)
        if existing_file:
            existing_file['content'] = content
            existing_file['category'] = category
        else:
            self.config_files.append({"path": file_path, "content": content, "category": category})

    async def _handle_service_validation(self, category: str):
        if category in self.config_categories:
            validation_result = await self.service_validator.validate_and_restart_service(category)
            if not validation_result['success']:
                return {"message": "Configuration validation failed", "details": validation_result}
        else:
            validation_result = {"success": True, "output": f"No validation/restart configuration for category: {category}"}
            self.logger.warning(f"No validation/restart configuration for category: {category}")
        
        return {"message": "Configuration updated successfully", "details": validation_result}
>>>>>>> c0f0e9e2ca8a70d1550a5e17304b46c7da3907f4

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

    async def add_new_config_category(self, category: str, key: str, validate_cmd: str, restart_cmd: str):
        """Add a new configuration category"""
        return await self.system_manager.add_new_config_category(category, key, validate_cmd, restart_cmd)