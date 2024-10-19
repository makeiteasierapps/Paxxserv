from typing import List
import os
from dotenv import load_dotenv
import shutil
import time
import logging
from ragatouille import RAGPretrainedModel

load_dotenv()

class ColbertService:
    def __init__(self, index_path=None, uid=None):
        is_local = os.getenv('LOCAL_DEV') == 'true'
        base_path = f'/mnt/media_storage/users/{uid}' if not is_local else os.path.join(os.getcwd(), f'media_storage/users/{uid}')
        self.index_root = os.path.join(base_path, '.ragatouille')

        if index_path and os.path.exists(index_path):
            self.rag = RAGPretrainedModel.from_index(index_path)
        else:
            self.rag = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0", index_root=self.index_root)
        self.index_path = index_path
    
    def process_content(self, content):
        try:
            if self.index_path is None or not os.path.exists(self.index_path):
                result = self.create_index(content)
                if result and 'index_path' in result:
                    self.index_path = result['index_path']
                    return {'index_path': self.index_path}
                else:
                    raise ValueError("Failed to create index")
            else:
                result = self.add_documents_to_index(content)
                return {'message': result}
        except Exception as e:
            logging.error(f"Error processing content: {str(e)}")
            raise
    
    def create_index(self, content: List[dict]):
        try:
            doc_ids = [doc['id'] for doc in content]
            collection = [doc['content'] for doc in content]
            metadata = [doc['metadata'] for doc in content]
            
            if not doc_ids or not collection:
                raise ValueError("No documents to index")
            
            index_name = f"index_{int(time.time())}"
            
            path = self.rag.index(
                index_name=index_name,
                collection=collection,
                document_ids=doc_ids,
                document_metadatas=metadata
            )
            return {'index_path': path}
        except ValueError as ve:
            print(f"ValueError in create_index: {ve}")
            return None
        except Exception as e:
            print(f"Error creating index: {e}")
            return None
    
    def delete_index(self):
        try:
            if not os.path.exists(self.index_path):
                logging.warning("Index path %s not found", self.index_path)
                return f'Index path {self.index_path} not found'

            logging.info("Attempting to delete index at: %s", self.index_path)
            if not os.path.isdir(self.index_path):
                logging.warning("Index path %s is not a directory", self.index_path)
                return f'Index path {self.index_path} is not a directory'

            shutil.rmtree(self.index_path)
            logging.info("Index directory %s deleted", self.index_path)
            return f'Index directory {self.index_path} deleted'

        except Exception as e:
            logging.error("Error deleting index: %s", str(e))
            return False
    
    def add_documents_to_index(self, content):
        try:
            doc_ids = [doc['id'] for doc in content]
            collection = [doc['content'] for doc in content]
            metadata = [doc['metadata'] for doc in content] | []
            self.rag.add_to_index(
                new_collection=collection,
                new_document_ids=doc_ids,
                new_document_metadatas=metadata
            )
            return 'Documents added to index'
        except Exception as e:
            print(f"Error adding documents to index: {e}")
            return False
    
    def delete_document_from_index(self, doc_sources):
        try:
            if not self.index_path:
                raise ValueError("No index path available")

            self.rag.delete_from_index(document_ids=doc_sources)
            return 'Documents deleted from index'
        except Exception as e:
            logging.error(f"Error deleting documents from index: {e}")
            return False
        
    def search_index(self, query):
        if not self.index_path:
            raise ValueError("An index path is required to query an index")
        return self.rag.search(query)
        
    def prepare_vector_response(self, query_results):
        text = []
        for item in query_results:
            if item['rank'] == 1:
                text.append(item['content'])
        combined_text = ' '.join(text)
        query_instructions = f'''
        \nAnswer the users question based off of the knowledge base provided below, provide 
        a detailed response that is relevant to the users question.\n
        KNOWLEDGE BASE: {combined_text}
        '''

        return query_instructions
