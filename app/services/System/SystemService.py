import os
import logging
from fastapi import HTTPException
from dotenv import load_dotenv
from app.utils.token_counter import token_counter
from app.services.System.SSHManager import SSHManager
from app.services.System.ConfigFileManager import ConfigFileManager
from app.services.System.ServiceValidator import ServiceValidator
from app.services.System.SystemConfigDatabase import SystemConfigDatabase

load_dotenv(override=True)

class SystemService:
    def __init__(self, db, uid):
        self.config_db = SystemConfigDatabase(db, uid)
        self.logger = logging.getLogger(__name__)
        self.is_dev_mode = os.getenv('LOCAL_DEV') == 'true'
        self.dev_server_ip = 'myserver.local'
        self.uid = uid

        self._verify_user()

        self.ssh_manager = SSHManager(self.is_dev_mode, self.logger)
        self.config_file_manager = ConfigFileManager(self.is_dev_mode, self.logger)

        # Load configurations from database
        config = self.config_db.fetch_user_config()
        self.config_files = config.get('config_files', [])
        self.config_categories = {cat['name']: cat for cat in config.get('config_categories', [])}
        self.service_validator = ServiceValidator(self.is_dev_mode, self.logger, self.config_categories)

    def get_systemd_services(self):
        file_path_list = [file['path'] for file in self.config_files if file['category'] == 'SystemD Service Files']
        file_names = [file_path.split('/')[-1] for file_path in file_path_list]
        return file_names

    def check_systemd_services(self):
        return self.service_validator.check_systemd_services(self.get_systemd_services())
    
    def _verify_user(self):
        try:
            self.config_db.check_if_user_authorized()
        except HTTPException as e:
            self.logger.error(f"User {self.uid} is not authorized to access this resource")
            raise e

    async def combine_config_files_by_category(self):
        category_contents = {}

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

    async def read_config_file(self, filename: str):
        ssh_client = self.ssh_manager.get_client() if self.is_dev_mode else None
        try:
            return await self.config_file_manager.read_file(filename, ssh_client)
        finally:
            if ssh_client:
                ssh_client.close()

    async def check_if_config_file_exists_on_server(self, filename: str):
        ssh_client = self.ssh_manager.get_client() if self.is_dev_mode else None
        try:
            return await self.config_file_manager.check_if_file_exists(filename, ssh_client)
        finally:
            if ssh_client:
                ssh_client.close()