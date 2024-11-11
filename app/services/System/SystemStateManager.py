from fastapi import FastAPI, HTTPException
from typing import Dict, Optional, List
import asyncio
import logging
import os
from dotenv import load_dotenv
from app.utils.token_counter import token_counter
from app.services.System.SSHManager import SSHManager
from app.services.System.ConfigFileManager import ConfigFileManager
from app.services.System.ServiceValidator import ServiceValidator
from app.services.System.SystemConfigDatabase import SystemConfigDatabase

load_dotenv(override=True)

class SystemStateManager:
    _instance: Optional['SystemStateManager'] = None
    _lock = asyncio.Lock()

    def __init__(self, db,):
        self.config_db = SystemConfigDatabase(db)
        self.logger = logging.getLogger(__name__)
        self.is_dev_mode = os.getenv('LOCAL_DEV') == 'true'
        self.dev_server_ip = 'myserver.local'
        
        # Shared state
        self.config_files: Dict = {}
        self.config_categories: Dict = {}
        
        # Managers
        self.ssh_manager = SSHManager(self.is_dev_mode, self.logger)
        self.config_file_manager = ConfigFileManager(self.is_dev_mode, self.logger)
        self.service_validator = None  # Will be initialized after loading config

    @classmethod
    async def get_instance(cls, db) -> 'SystemStateManager':
        if not cls._instance:
            async with cls._lock:
                if not cls._instance:
                    cls._instance = cls(db)
                    await cls._instance.initialize()
        return cls._instance

    async def initialize(self):
        """Load initial configuration from database"""
        print(self.config_db.config_collection)
        # Find all documents in the collection
        config_data = await self.config_db.config_collection.find_one({})
        if config_data:
            self.config_files = {file['path']: file for file in config_data.get('config_files', [])}
            self.config_categories = {cat['name']: cat for cat in config_data.get('config_categories', [])}
        else:
            self.config_files = {}
            self.config_categories = {}
        self.service_validator = ServiceValidator(self.is_dev_mode, self.logger, self.config_categories)

    async def get_config_files(self):
        """Fetch config files from database"""
        config_data = await self.config_db.config_collection.find_one({})
        return config_data.get('config_files', []) if config_data else []

    def get_systemd_services(self) -> List[str]:
        """Get list of SystemD service file names"""
        file_names = [
            path.split('/')[-1] 
            for path, file in self.config_files.items() 
            if file['category'] == 'SystemD Service Files'
        ]
        return file_names

    def check_systemd_services(self):
        """Check status of SystemD services"""
        return self.service_validator.check_systemd_services(self.get_systemd_services())

    async def combine_config_files_by_category(self):
        """Combine and update config files by category"""
        async with self._lock:
            category_contents = {}

            # Combine contents by category
            for file_info in self.config_files.values():
                category = file_info['category']
                path = file_info['path']
                content = file_info['content']

                if category not in category_contents:
                    category_contents[category] = ""

                category_contents[category] += f"{path}\n{content}\n\n"

            # Create combined files collection
            combined_files = [
                {
                    "category": category,
                    "content": content,
                    "token_count": token_counter(content)
                }
                for category, content in category_contents.items()
            ]

            # Update database
            await self.config_db.update_combined_files(combined_files)
            return combined_files

    async def add_new_config_category(self, category: str, key: str, validate_cmd: str, restart_cmd: str):
        """Add a new configuration category"""
        async with self._lock:
            if category not in self.config_categories:
                category_data = {
                    'name': category,
                    'key': key,
                    'validate_cmd': validate_cmd,
                    'restart_cmd': restart_cmd
                }
                self.config_categories[category] = category_data
                await self.config_db.update_config_categories(list(self.config_categories.values()))

    async def update_config_file(self, file_path: str, content: str, category: str, uid: str):
        """Update a configuration file"""
        async with self._lock:
            file_path = '/' + file_path.lstrip('/')
            ssh_client = self.ssh_manager.get_client() if self.is_dev_mode else None
            
            try:
                # Write to file system
                await self.config_file_manager.write_file(file_path, content, ssh_client)
                
                # Update database
                update_result = await self.config_db.update_or_insert_file(file_path, content, category)
                
                # Update in-memory state
                self.config_files[file_path] = {
                    "path": file_path,
                    "content": content,
                    "category": category
                }
                
                self.logger.info(f"Database update result: matched={update_result.matched_count}, modified={update_result.modified_count}")
                
                # Handle service validation
                validation_result = await self._handle_service_validation(category, file_path, uid)
                return validation_result

            except Exception as e:
                self.logger.error(f"Error writing to file {file_path}: {str(e)}")
                raise HTTPException(status_code=500, detail="Error writing to configuration file")
            finally:
                if ssh_client:
                    ssh_client.close()

    async def _handle_service_validation(self, category: str, file_path: str, uid: str):
        """Handle service validation and restart"""
        if category in self.config_categories:
            validation_result = await self.service_validator.validate_and_restart_service(category)
            if not validation_result['success']:
                return {"message": "Configuration validation failed", "details": validation_result}
        else:
            validation_result = {"success": True, "output": f"No validation/restart configuration for category: {category}"}
            self.logger.warning(f"No validation/restart configuration for category: {category}")
        
        self.logger.info(f"User {uid} updated file {file_path}")
        return {"message": "Configuration updated successfully", "details": validation_result}

    async def read_config_file(self, filename: str):
        """Read a configuration file"""
        ssh_client = self.ssh_manager.get_client() if self.is_dev_mode else None
        try:
            return await self.config_file_manager.read_file(filename, ssh_client)
        finally:
            if ssh_client:
                ssh_client.close()

    async def check_if_config_file_exists_on_server(self, filename: str):
        """Check if a configuration file exists on the server"""
        ssh_client = self.ssh_manager.get_client() if self.is_dev_mode else None
        try:
            return await self.config_file_manager.check_if_file_exists(filename, ssh_client)
        finally:
            if ssh_client:
                ssh_client.close()