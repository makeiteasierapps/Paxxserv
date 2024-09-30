from bson import ObjectId
from datetime import datetime, timezone
from dotenv import load_dotenv
import logging
load_dotenv()

class KnowledgeBaseService:
    def __init__(self, db, uid, kb_id=None, colbert_service=None, openai_client=None):
        self.db = db
        self.uid = uid
        self.kb_id = kb_id
        self.colbert_service = colbert_service
        self.openai_client = openai_client
        self.index_path = self.get_index_path() if kb_id else None

    def set_colbert_service(self, colbert_service):
        self.colbert_service = colbert_service

    def set_openai_client(self, openai_client):
        self.openai_client = openai_client
    
    def set_kb_id(self, kb_id):
        self.kb_id = kb_id
        self.index_path = self.get_index_path()
        return self.index_path

    def get_index_path(self):
        try:
            kb = self.db['knowledge_bases'].find_one({'_id': ObjectId(self.kb_id)})
            return kb['index_path'] if kb else None
        except Exception as e:
            logging.error(f"Error getting index path: {str(e)}")
            return None

    def get_kb_list(self, uid):
        try:
            kb_list_cursor = self.db['knowledge_bases'].find({'uid': uid})
            kb_list = [{'id': str(kb['_id']), **{k: v for k, v in kb.items() if k != '_id'}} for kb in kb_list_cursor]
            return kb_list if kb_list else []  # Return empty list if kb_list is empty
        except Exception as e:
            print(f"Error in get_kb_list: {e}")
            return []

    def delete_kb_by_id(self, kb_id):
        try:
            if not self.colbert_service:
                raise ValueError("ColbertService not initialized")
            self.colbert_service.delete_index(self.index_path)
            self.db['knowledge_bases'].delete_one({'_id': ObjectId(kb_id)})
            self.db['kb_docs'].delete_many({'kb_id': kb_id})
        except Exception as e:
            logging.error(f"Error deleting kb by id: {str(e)}")
            raise

    def create_new_kb(self, uid, name, objective):
        try:
            kb_details = {
                'name': name,
                'index_path': None,
                'uid': uid,
                'objective': objective,
                'documents': [],
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            new_kb = self.db['knowledge_bases'].insert_one(kb_details)
            kb_id = str(new_kb.inserted_id)
            kb_details['id'] = kb_id
            del kb_details['_id']
            return kb_details
        except Exception as e:
            logging.error(f"Error creating new kb: {str(e)}")
            raise
