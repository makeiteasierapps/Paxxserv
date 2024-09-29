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
            self.rag = RAGPretrainedModel.from_index(index_path, n_gpu=0)
        else:
            self.rag = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0", index_root=self.index_root, n_gpu=0)
        self.index_path = index_path
    
    def process_content(self, index_path, content):
        try:
            if index_path is None or not os.path.exists(index_path):
                index_path = self.create_index(content)['index_path']
                print(f"Index path: {index_path}")
                return {'index_path': index_path}
            else:
                return self.add_documents_to_index(content)
        except Exception as e:
            logging.error(f"Error processing content: {str(e)}")
            raise
    
    def create_index(self, content):
        try:
            doc_objs = self._prepare_documents(content)
            doc_ids = [doc['id'] for doc in doc_objs]
            collection = [doc['content'] for doc in doc_objs]
            index_name = f"index_{int(time.time())}"  # Generate a unique name
            path = self.rag.index(
                index_name=index_name,
                collection=collection,
                document_ids=doc_ids,
                use_faiss=True
            )
            return {'index_path': path}
        except Exception as e:
            print(f"Error creating index: {e}")
            return None
    
    def delete_index(self, index_path):
        try:
            if os.path.exists(index_path):
                index_name = os.path.basename(index_path)
                index_dir = os.path.join('.ragatouille', 'colbert', 'indexes', index_name)
                if os.path.exists(index_dir):
                    shutil.rmtree(index_dir)
                    return f'Index {index_name} deleted'
                else:
                    return f'Index directory for {index_name} not found'
            else:
                return f'Index path {index_path} not found'
        except Exception as e:
            print(f"Error deleting index: {e}")
            return False
    
    def add_documents_to_index(self, content):
        try:
            doc_objs = self._prepare_documents(content)
            doc_ids = [doc['id'] for doc in doc_objs]
            collection = [doc['content'] for doc in doc_objs]
            self.rag.add_to_index(
                new_collection=collection,
                new_document_ids=doc_ids
            )
            return 'Documents added to index'
        except Exception as e:
            print(f"Error adding documents to index: {e}")
            return False
    
    def delete_document_from_index(self, doc_id):
        try:
            self.rag.delete_from_index(document_ids=[doc_id])
            return 'Document deleted from index'
        except Exception as e:
            print(f"Error deleting document from index: {e}")
            return False

    def _prepare_documents(self, content):
        if isinstance(content, list):
            return [{'content': doc['content'], 'id': doc['metadata']['sourceURL']} for doc in content if 'content' in doc and 'metadata' in doc and 'sourceURL' in doc['metadata']]
        else:
            raise ValueError("Content must be either a string or a list of dictionaries with 'content' key")
        
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
