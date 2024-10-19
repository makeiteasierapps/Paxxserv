class SystemIndexManager:
    def __init__(self, system_service, colbert_service):
        self.system_service = system_service
        self.colbert_service = colbert_service

    def prepare_config_files_for_indexing(self):
        config_files = self.system_service.config_files
        prepared_data = []

        for config_file in config_files:
            prepared_data.append({
                'id': config_file['path'],
                'content': config_file['content'],
                'metadata': {
                    'path': config_file['path'],
                    'category': config_file['category']
                }
            })

        return prepared_data
    
    def create_system_index(self, content):
        return self.colbert_service.create_index(content)
