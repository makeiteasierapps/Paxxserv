import time
from ragatouille import RAGPretrainedModel


class ColbertService:
    def __init__(self):
        self.rag = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0")
    
    def process_content(self, index_path, content):
        if index_path is None:
            return self.create_index(content)
        else:
            return self.add_documents_to_index(index_path, content)
    
    def create_index(self, content):
        documents = self._prepare_documents(content)
        index_name = f"index_{int(time.time())}"  # Generate a unique name
        path = self.rag.index(
            index_name=index_name,
            collection=documents,
        )
        return path
    
    def add_documents_to_index(self, index_name, content):
        try:
            documents = self._prepare_documents(content)
            print(documents)
            self.rag.add_to_index(
                index_name=index_name,
                new_collection=documents,
            )
            return True
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