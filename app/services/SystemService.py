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
        
        self.config_files = [
            '/etc/nginx/sites-available/default',
            '/etc/systemd/system/paxxserv.service',
            '/etc/systemd/system/firecrawl.service'
        ]

    async def list_config_files(self, uid):
        user = self.user_service.get_user(uid)
        if not user or not user.get('is_admin', False):
            raise HTTPException(status_code=403, detail="Unauthorized access")
        return self.config_files

    async def read_multiple_config_files(self, uid: str, filenames):
        user = self.user_service.get_user(uid)
        if not user or not user.get('is_admin', False):
            raise HTTPException(status_code=403, detail="Unauthorized access")
        
        result = []
        valid_filenames = [f for f in filenames if f in self.config_files]
        
        if self.is_dev_mode:
            result = await self._read_multiple_remote_files(valid_filenames)
        else:
            for filename in valid_filenames:
                try:
                    with open(filename, 'r') as file:
                        content = file.read()
                    result.append({"filename": filename, "content": content})
                except Exception as e:
                    self.logger.error(f"Error reading file {filename}: {str(e)}")
                    result.append({"filename": filename, "content": f"Error: {str(e)}"})
        
        # Add any invalid filenames to the result
        for filename in filenames:
            if filename not in valid_filenames:
                result.append({"filename": filename, "content": "Error: File not found"})
        
        return result
    
    async def _read_multiple_remote_files(self, filenames):
        ssh = None
        try:
            ssh = self._get_ssh_client()
            sftp = ssh.open_sftp()
            result = []
            for filename in filenames:
                try:
                    with sftp.file(filename, 'r') as remote_file:
                        content = remote_file.read().decode('utf-8')
                    result.append({"filename": filename, "content": content})
                except Exception as e:
                    self.logger.error(f"Error reading remote file {filename}: {str(e)}")
                    result.append({"filename": filename, "content": f"Error: {str(e)}"})
            return result
        except Exception as e:
            self.logger.error(f"Error connecting to remote server: {str(e)}")
            raise
        finally:
            if ssh:
                ssh.close()

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
        ssh = None
        try:
            ssh = self._get_ssh_client()
            sftp = ssh.open_sftp()
            with sftp.file(filename, 'r') as remote_file:
                content = remote_file.read().decode('utf-8')
            return content
        except Exception as e:
            self.logger.error(f"Error reading remote file {filename}: {str(e)}")
            raise
        finally:
            if ssh:
                ssh.close()

    async def _write_remote_file(self, filename, content):
        ssh = None
        try:
            ssh = self._get_ssh_client()
            sftp = ssh.open_sftp()
            with sftp.file(filename, 'w') as remote_file:
                remote_file.write(content)
        except Exception as e:
            self.logger.error(f"Error writing to remote file {filename}: {str(e)}")
            raise
        finally:
            if ssh:
                ssh.close()

    def _get_ssh_client(self):
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_key_path = os.path.expanduser('~/.ssh/abyssus')
        ssh.connect(
            self.dev_server_ip,
            username=os.getenv('SERVER_USERNAME'),
            key_filename=ssh_key_path
        )
        return ssh