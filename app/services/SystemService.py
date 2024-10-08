import os
import logging
from fastapi import HTTPException
from dotenv import load_dotenv
from app.services.UserService import UserService

load_dotenv()

class SystemService:
    def __init__(self, db, user_service: UserService):
        self.db = db
        self.user_service = user_service
        self.logger = logging.getLogger(__name__)
        self.is_dev_mode = os.getenv('LOCAL_DEV') == 'true'
        self.dev_server_ip = 'myserver.local'
        
        if self.is_dev_mode:
            self.config_files = [
                '/tmp/nginx_sites_available_default',
                '/tmp/paxxserv.service',
                '/tmp/firecrawl.service'
            ]
        else:
            self.config_files = [
                '/etc/nginx/sites-available/default',
                '/etc/systemd/system/paxxserv.service',
                '/etc/systemd/system/firecrawl.service'
            ]

    async def list_config_files(self, uid: str):
        user = self.user_service.get_user(uid)
        if not user or not user.get('is_admin', False):
            raise HTTPException(status_code=403, detail="Unauthorized access")
        return self.config_files

    async def read_config_file(self, uid: str, filename: str):
        user = self.user_service.get_user(uid)
        if not user or not user.get('is_admin', False):
            raise HTTPException(status_code=403, detail="Unauthorized access")
        
        if filename not in self.config_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        try:
            if self.is_dev_mode:
                content = await self._read_remote_file(filename)
            else:
                with open(filename, 'r') as file:
                    content = file.read()
            return content
        except Exception as e:
            self.logger.error(f"Error reading file {filename}: {str(e)}")
            raise HTTPException(status_code=500, detail="Error reading configuration file")

    async def write_config_file(self, uid: str, filename: str, content: str):
        user = self.user_service.get_user(uid)
        if not user or not user.get('is_admin', False):
            raise HTTPException(status_code=403, detail="Unauthorized access")
        
        if filename not in self.config_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        try:
            if self.is_dev_mode:
                await self._write_remote_file(filename, content)
            else:
                with open(filename, 'w') as file:
                    file.write(content)
            self.logger.info(f"User {uid} updated file {filename}")
            return {"message": "File updated successfully"}
        except Exception as e:
            self.logger.error(f"Error writing to file {filename}: {str(e)}")
            raise HTTPException(status_code=500, detail="Error writing to configuration file")

    async def _read_remote_file(self, filename):
        import paramiko
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.dev_server_ip, username=os.getenv('SERVER_USERNAME'))
        
        sftp = ssh.open_sftp()
        with sftp.file(filename, 'r') as remote_file:
            content = remote_file.read().decode('utf-8')
        
        ssh.close()
        return content

    async def _write_remote_file(self, filename, content):
        import paramiko
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.dev_server_ip, username=os.getenv('SERVER_USERNAME'))
        
        sftp = ssh.open_sftp()
        with sftp.file(filename, 'w') as remote_file:
            remote_file.write(content)
        
        ssh.close()