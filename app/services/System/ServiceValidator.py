import asyncio
from app.services.System.SSHManager import SSHManager

class ServiceValidator:
    def __init__(self, is_dev_mode, logger, config_categories):
        self.is_dev_mode = is_dev_mode
        self.logger = logger
        self.config_categories = config_categories
        self.ssh_manager = SSHManager(self.is_dev_mode, self.logger)

    async def validate_and_restart_service(self, category):
        ssh_client = self.ssh_manager.get_client() if self.is_dev_mode else None
        try:
            return await self._validate_and_restart_service(category, ssh_client)
        finally:
            if ssh_client:
                ssh_client.close()

    async def _validate_and_restart_service(self, category, ssh=None):
        service_info = self.config_categories.get(category)
        if not service_info:
            self.logger.warning(f"No validation/restart configuration for category: {category}")
            return {"success": True, "output": f"No validation/restart configuration for category: {category}"}

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

    async def _run_local_command(self, command):
        try:
            # Run command asynchronously
            process = await asyncio.create_subprocess_exec(
                *command.split(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                self.logger.error(f"Error executing command {command}: {stderr.decode()}")
                raise Exception(f"Error executing command: {stderr.decode()}")

            self.logger.info(f"Command executed successfully: {command}")
            return stdout.decode()
        except Exception as e:
            self.logger.error(f"Exception occurred: {str(e)}")
            raise e