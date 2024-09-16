import os
import time
from ragatouille import RAGPretrainedModel


class ColbertService:
    def __init__(self, index_path=None):
        if index_path and os.path.exists(index_path):
            self.rag = RAGPretrainedModel.from_index(index_path)
        else:
            self.rag = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0")
        self.index_path = index_path
    
    def process_content(self, index_path, content):
        if index_path is None or not os.path.exists(index_path):
            return self.create_index(content)
        else:
            return self.add_documents_to_index(content)
    
    def create_index(self, content):
        try:
            documents = self._prepare_documents(content)
            print('Creating index with documents:', documents)
            index_name = f"index_{int(time.time())}"  # Generate a unique name
            path = self.rag.index(
                index_name=index_name,
                collection=documents,
            )
            return {'index_path': path}
        except Exception as e:
            print(f"Error creating index: {e}")
            return None
    
    def add_documents_to_index(self, content):
        try:
            documents = self._prepare_documents(content)
            print('Adding documents to index:', documents)
            self.rag.add_to_index(
                new_collection=documents,
            )
            return 'Documents added to index'
        except Exception as e:
            print(f"Error adding documents to index: {e}")
            return False
    
    def _prepare_documents(self, content):
        if isinstance(content, str):
            return [content]
        elif isinstance(content, list):
            return [doc['content'] for doc in content if 'content' in doc]
        else:
            raise ValueError("Content must be either a string or a list of dictionaries with 'content' key")