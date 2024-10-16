import os
import asyncio

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

    async def check_if_file_exists(self, filename: str, ssh_client=None):
        if self.is_dev_mode:
            content = await self._read_remote_file(filename, ssh_client)
            return content is not None
        else:
            return os.path.exists(filename)

    async def _read_remote_file(self, filename, ssh):
        try:
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
            ssh.close()

    def _read_local_file(self, filename):
        with open(filename, 'r') as file:
            return file.read()

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
