import os
import asyncio
import subprocess
class ConfigFileManager:
    def __init__(self, is_dev_mode, logger):
        self.is_dev_mode = is_dev_mode
        self.logger = logger

    async def write_file(self, file_path: str, content: str, ssh_client=None):
        if self.is_dev_mode:
            await self._write_remote_file(file_path, content, ssh_client)
        else:
            await self._write_local_file_with_sudo(file_path, content)

    async def read_file(self, filename: str, ssh_client=None):
        if self.is_dev_mode:
            return await self._read_remote_file(filename, ssh_client)
        else:
            return self._read_local_file(filename)

    async def create_file(self, filename: str, ssh_client=None):
        """Create an empty file at the specified path."""
        if self.is_dev_mode:
            await self._create_remote_file(filename, ssh_client)
        else:
            await self._create_local_file(filename)

    async def _create_remote_file(self, filename, ssh):
        try:
            # Use touch command with sudo to create the file
            sudo_command = f"sudo touch {filename}"
            stdin, stdout, stderr = ssh.exec_command(sudo_command)
            
            error = stderr.read().decode('utf-8').strip()
            if error:
                raise Exception(f"Error creating file: {error}")
            
            self.logger.info(f"Successfully created remote file {filename}")
        except Exception as e:
            self.logger.error(f"Error creating remote file {filename}: {str(e)}")
            raise
    
    async def _create_local_file(self, filename: str):
        try:
            sudo_command = f"sudo -n /usr/local/bin/create_config_file.sh {filename}"

            # Run sudo command asynchronously
            process = await asyncio.create_subprocess_exec(
                *sudo_command.split(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise Exception(f"Sudo command failed: {stderr.decode()}")

            self.logger.info(f"Successfully created local file {filename}")
        except Exception as e:
            self.logger.error(f"Error creating local file {filename}: {str(e)}")
            raise
    
    async def check_if_file_exists(self, filename: str, ssh_client=None):
        if self.is_dev_mode:
            content = await self._read_remote_file(filename, ssh_client)
            return content is not None
        else:
            return os.path.exists(filename)

    async def _read_remote_file(self, filename, ssh):
        try:
            # Use sudo to read the file content
            sudo_command = f"sudo cat {filename}"
            stdin, stdout, stderr = ssh.exec_command(sudo_command)
            
            error = stderr.read().decode('utf-8').strip()
            if error:
                raise Exception(f"Error reading file: {error}")
                
            content = stdout.read().decode('utf-8')
            return content
        except Exception as e:
            self.logger.error(f"Error accessing remote file {filename}: {str(e)}")
            return None
        finally:
            ssh.close()

    def _read_local_file(self, filename):
        try:
            # Use sudo for reading privileged files
            sudo_command = f"sudo -n /usr/local/bin/read_config_file.sh {filename}"
            
            # Run the command synchronously since this is not an async method
            process = subprocess.run(
                sudo_command.split(),
                capture_output=True,
                text=True,
                check=False  # Don't raise CalledProcessError if command fails
            )

            if process.returncode != 0:
                raise Exception(f"Failed to read file: {process.stderr}")

            return process.stdout
        except Exception as e:
            self.logger.error(f"Error reading local file {filename}: {str(e)}")
            raise

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
            sudo_command = f"sudo -n /usr/local/bin/write_config_file.sh {filename}"

            # Run sudo command asynchronously
            process = await asyncio.create_subprocess_exec(
                *sudo_command.split(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate(input=content.encode())

            if process.returncode != 0:
                raise Exception(f"Sudo command failed: {stderr.decode()}")

            self.logger.info(f"Successfully wrote to local file {filename}")
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")
            raise e
