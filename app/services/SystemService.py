import os
import subprocess
import logging
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

class SystemService:
    def __init__(self, db, user_service, uid):
        self.db = db
        self.user_service = user_service
        self.logger = logging.getLogger(__name__)
        self.is_dev_mode = os.getenv('LOCAL_DEV') == 'true'
        self.dev_server_ip = 'myserver.local'
        self.uid = uid
        
        # Verify user and load config files on initialization
        user = self.user_service.get_user(uid)
        if not user or not user.get('is_admin', False):
            raise HTTPException(status_code=403, detail="Unauthorized access")
        
        self.config_files = self._get_config_files_from_db()

    def _get_config_files_from_db(self):
        config = self.db.system_config.find_one({"uid": self.uid})
        if config:
            return config.get('config_files', [])
        return []

    def refresh_config_files(self):
        self.config_files = self._get_config_files_from_db()

    async def write_config_file(self, filename: str, content: str):
        filename = '/' + filename.lstrip('/')
        if filename not in [item['path'] for item in self.config_files]:
            raise HTTPException(status_code=404, detail="File not found")
        
        try:
            # Write to remote server or local file system
            if self.is_dev_mode:
                await self._write_remote_file(filename, content)
            else:
                await self._write_local_file_with_sudo(filename, content)
            
            # Update the content in the database
            self.db.system_config.update_one(
                {"uid": self.uid, "config_files.path": filename},
                {"$set": {"config_files.$.content": content}},
                upsert=True
            )
            
            self.logger.info(f"User {self.uid} updated file {filename}")
            return {"message": "File updated successfully"}
        except Exception as e:
            self.logger.error(f"Error writing to file {filename}: {str(e)}")
            raise HTTPException(status_code=500, detail="Error writing to configuration file")

    def _read_local_file(self, filename):
        with open(filename, 'r') as file:
            return file.read()

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
            # Use sudo to write the file content
            sudo_command = f"sudo tee {filename}"
            stdin, stdout, stderr = ssh.exec_command(sudo_command)
            stdin.write(content)
            stdin.channel.shutdown_write()
            
            # Check for any errors
            error = stderr.read().decode('utf-8').strip()
            if error:
                raise Exception(f"Error writing file: {error}")
            
            self.logger.info(f"Successfully wrote to remote file {filename}")
        except Exception as e:
            self.logger.error(f"Error writing to remote file {filename}: {str(e)}")
            raise
        finally:
            if ssh:
                ssh.close()

    async def _write_local_file_with_sudo(self, filename: str, content: str):
        try:
            # Use a specific sudo command that only allows writing to certain files
            sudo_command = f"sudo -n /usr/local/bin/write_config_file.sh {filename}"
            
            # Use subprocess.run with input parameter to avoid shell injection
            result = subprocess.run(
                sudo_command.split(),
                input=content.encode(),
                capture_output=True,
                check=True
            )
            
            if result.returncode != 0:
                raise Exception(f"Sudo command failed: {result.stderr.decode()}")
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error executing sudo command: {e.stderr.decode()}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")

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
