import os
import subprocess
import logging
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv(override=True)

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
        self.config_categories = self._get_config_categories_from_db()

    def _get_config_categories_from_db(self):
        config = self.db.system_config.find_one({"uid": self.uid})
        if config and 'config_categories' in config:
            return {cat['name']: cat for cat in config['config_categories']}
        return {}

    def _get_config_files_from_db(self):
        config = self.db.system_config.find_one({"uid": self.uid})
        if config:
            return config.get('config_files', [])
        return []

    def add_new_config_category(self, category: str, key: str, validate_cmd: str, restart_cmd: str):
        # Check if the category already exists
        if category in self.config_categories:
            return

        # Add the new category
        self.config_categories[category] = {
            'name': category,
            'key': key,
            'validate_cmd': validate_cmd,
            'restart_cmd': restart_cmd
        }
        
        # Update the database
        self.db.system_config.update_one(
            {"uid": self.uid},
            {"$set": {"config_categories": list(self.config_categories.values())}}
        )

    def refresh_config_files(self):
        self.config_files = self._get_config_files_from_db()

    async def write_config_file(self, file_path: str, content: str, category: str):
        file_path = '/' + file_path.lstrip('/')    
        ssh = None
        try:
            if self.is_dev_mode:
                ssh = self._get_ssh_client()

            # Write to remote server or local file system
            if self.is_dev_mode:
                await self._write_remote_file(file_path, content, ssh)
            else:
                await self._write_local_file_with_sudo(file_path, content)

            # Update or insert the content in the database
            update_result = self.db.system_config.update_one(
                {"uid": self.uid, "config_files.path": file_path},
                {
                    "$set": {
                        "config_files.$.content": content,
                        "config_files.$.category": category
                    }
                }
            )

            self.logger.info(f"Database update result: matched={update_result.matched_count}, modified={update_result.modified_count}")

            # If the file wasn't updated (i.e., it's new), add it to the array
            if update_result.matched_count == 0:
                push_result = self.db.system_config.update_one(
                    {"uid": self.uid},
                    {"$push": {"config_files": {"path": file_path, "content": content, "category": category}}},
                    upsert=True
                )

                self.logger.info(f"New file pushed to database: matched={push_result.matched_count}, modified={push_result.modified_count}")

            # Update the in-memory config_files list
            existing_file = next((item for item in self.config_files if item['path'] == file_path), None)
            if existing_file:
                existing_file['content'] = content
                existing_file['category'] = category
            else:
                self.config_files.append({"path": file_path, "content": content, "category": category})

            # Validate and restart affected services
            if category in self.config_categories:
                validation_result = await self._validate_and_restart_service(category, ssh)
                if not validation_result['success']:
                    # Revert the changes if validation fails
                    await self._revert_file_changes(file_path, ssh)
                    return {"message": "Configuration validation failed", "details": validation_result}
            else:
                validation_result = {"success": True, "output": f"No validation/restart configuration for category: {category}"}
                self.logger.warning(f"No validation/restart configuration for category: {category}")
            
            self.logger.info(f"User {self.uid} updated file {file_path}")
            return {"message": "File updated successfully and services restarted", "details": validation_result}
        except Exception as e:
            self.logger.error(f"Error writing to file {file_path}: {str(e)}")
            raise HTTPException(status_code=500, detail="Error writing to configuration file")
        finally:
            if ssh:
                ssh.close()
    
    async def _validate_and_restart_service(self, category, ssh=None):
        service_info = self.config_categories[category]
        result = {
            'category': category,
            'validation': {'success': False, 'output': ''},
            'restart': {'success': False, 'output': ''}
        }
        
        try:
            # Validate configuration
            validation_output = await self._run_command(service_info['validate_cmd'], ssh)
            result['validation'] = {'success': True, 'output': validation_output}
            
            # Restart service
            restart_output = await self._run_command(service_info['restart_cmd'], ssh)
            result['restart'] = {'success': True, 'output': restart_output}
            
            self.logger.info(f"Validated and restarted service for category: {category}")
            result['success'] = True
        except Exception as e:
            self.logger.error(f"Error during validation or restart for category {category}: {str(e)}")
            result['success'] = False
            result['error'] = str(e)
        
        return result
    
    async def _run_command(self, command, ssh=None):
        if self.is_dev_mode:
            return await self._run_remote_command(command, ssh)
        else:
            return await self._run_local_command(command)

    async def _run_local_command(self, command):
        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                check=True,
                text=True
            )
            self.logger.info(f"Command executed successfully: {command}")
            return result.stdout
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error executing command {command}: {e.stderr}")
            raise Exception(f"Error executing command: {e.stderr}")

    async def _run_remote_command(self, command, ssh):
        try:
            stdin, stdout, stderr = ssh.exec_command(command)
            
            # Read both stdout and stderr
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            # Combine output and error for logging purposes
            full_output = output + '\n' + error if error else output
            
            # Check if the command was successful based on exit status
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                raise Exception(f"Command failed with exit status {exit_status}: {full_output}")
            
            self.logger.info(f"Command executed successfully on remote: {command}")
            self.logger.info(f"Command output: {full_output}")
            return full_output
        except Exception as e:
            self.logger.error(f"Error executing remote command {command}: {str(e)}")
            raise
    
    async def _revert_file_changes(self, filename, ssh=None):
        # Implement logic to revert file changes
        # This could involve restoring from a backup or fetching the previous version from the database
        pass

    async def read_config_file(self, filename: str):
        print(filename)
        if self.is_dev_mode:
            return await self._read_remote_file(filename)
        else:
            return self._read_local_file(filename)
        
    def _read_local_file(self, filename):
        with open(filename, 'r') as file:
            return file.read()

    async def _read_remote_file(self, filename):
        ssh = None
        try:
            ssh = self._get_ssh_client()
            sftp = ssh.open_sftp()
            try:
                with sftp.file(filename, 'r') as remote_file:
                    content = remote_file.read().decode('utf-8')
                return content
            except FileNotFoundError:
                return None
        except Exception as e:
            self.logger.error(f"Error accessing remote file {filename}: {str(e)}")
            return None
        finally:
            if ssh:
                ssh.close()

    async def _write_remote_file(self, filename, content, ssh):
        try:
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
            self.logger.info(f"Successfully wrote to local file {filename}")
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
    
    async def check_if_config_file_exists_on_server(self, filename: str):
        if self.is_dev_mode:
            content = await self._read_remote_file(filename)
            return content is not None
        else:
            return os.path.exists(filename)