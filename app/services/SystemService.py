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

        self.config_categories = {
            'nginx': {
                'validate_cmd': 'sudo nginx -t',
                'restart_cmd': 'sudo systemctl restart nginx'
            },
            'systemd': {
                'validate_cmd': 'sudo systemd-analyze verify',
                'restart_cmd': 'sudo systemctl daemon-reload'
            },
            'fstab': {
                'validate_cmd': 'sudo findmnt --verify',
                'restart_cmd': 'sudo mount -a'
            },
            'ssh': {
                'validate_cmd': 'sudo sshd -t',
                'restart_cmd': 'sudo systemctl restart sshd'
            },
            'dns': {
                'validate_cmd': 'sudo named-checkconf',
                'restart_cmd': 'sudo systemctl restart named'
            },
            'logrotate': {
                'validate_cmd': 'sudo logrotate -d /etc/logrotate.conf',
                'restart_cmd': 'sudo systemctl restart logrotate'
            },
            'user_group': {
                'validate_cmd': 'sudo pwck -r',
                'restart_cmd': 'sudo nscd -i passwd -i group'
            },
            'sysctl': {
                'validate_cmd': 'sudo sysctl --system',
                'restart_cmd': 'sudo sysctl --system'
            },
            'environment': {
                'validate_cmd': 'sudo -E bash -c "source /etc/environment && env"',
                'restart_cmd': 'sudo systemctl daemon-reload'
            },
            'fail2ban': {
                'validate_cmd': 'sudo fail2ban-client -t',
                'restart_cmd': 'sudo systemctl restart fail2ban'
            }
        }

        self.category_mapping = {
            'NGINX Configuration': 'nginx',
            'SystemD Service Files': 'systemd',
            'FSTAB for File System Mounting': 'fstab',
            'SSH Configuration': 'ssh',
            'DNS and Networking': 'dns',
            'Logrotate for Log Management': 'logrotate',
            'User and Group Configuration': 'user_group',
            'Sysctl for Kernel Parameters': 'sysctl',
            'Environment Variables': 'environment',
            'Fail2ban Configuration': 'fail2ban'
        }
    
    def _get_config_files_from_db(self):
        config = self.db.system_config.find_one({"uid": self.uid})
        if config:
            return config.get('config_files', [])
        return []

    def refresh_config_files(self):
        self.config_files = self._get_config_files_from_db()

    async def write_config_file(self, filename: str, content: str, category: str):
        mapped_category = self.category_mapping.get(category)
        filename = '/' + filename.lstrip('/')
        if filename not in [item['path'] for item in self.config_files]:
            raise HTTPException(status_code=404, detail="File not found")
        
        ssh = None
        try:
            if self.is_dev_mode:
                ssh = self._get_ssh_client()
            
            # Write to remote server or local file system
            if self.is_dev_mode:
                await self._write_remote_file(filename, content, ssh)
            else:
                await self._write_local_file_with_sudo(filename, content)
            
            # Update the content in the database
            self.db.system_config.update_one(
                {"uid": self.uid, "config_files.path": filename},
                {"$set": {"config_files.$.content": content}},
                upsert=True
            )
            
            # Validate and restart affected services
            if mapped_category in self.config_categories:
                validation_result = await self._validate_and_restart_service(mapped_category, ssh)
                if not validation_result['success']:
                    # Revert the changes if validation fails
                    await self._revert_file_changes(filename, ssh)
                    return {"message": "Configuration validation failed", "details": validation_result}
            else:
                self.logger.warning(f"No validation/restart configuration for category: {mapped_category}")
            
            self.logger.info(f"User {self.uid} updated file {filename}")
            return {"message": "File updated successfully and services restarted", "details": validation_result}
        except Exception as e:
            self.logger.error(f"Error writing to file {filename}: {str(e)}")
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
