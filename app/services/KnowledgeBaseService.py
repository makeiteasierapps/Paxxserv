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
        self.index_path = None
        if kb_id:
            # Note: This is not ideal as it makes an async call in __init__
            # Consider using a separate initialization method instead
            self.index_path = self.get_index_path()

    def set_colbert_service(self, colbert_service):
        self.colbert_service = colbert_service

    def set_openai_client(self, openai_client):
        self.openai_client = openai_client
    
    async def set_kb_id(self, kb_id):
        self.kb_id = kb_id
        self.index_path = await self.get_index_path()
        return self.index_path

    async def get_index_path(self):
        try:
            kb = await self.db['knowledge_bases'].find_one({'_id': ObjectId(self.kb_id)})
            return kb['index_path'] if kb else None
        except Exception as e:
            logging.error(f"Error getting index path: {str(e)}")
            return None

    async def get_kb_list(self, uid):
        try:
            kb_list = []
            cursor = self.db['knowledge_bases'].find({'uid': uid})
            async for kb in cursor:
                kb_list.append({
                    'id': str(kb['_id']), 
                    **{k: v for k, v in kb.items() if k != '_id'}
                })
            return kb_list
        except Exception as e:
            logging.error(f"Error in get_kb_list: {e}")
            return []

    async def delete_kb_by_id(self, kb_id):
        try:
            if not self.colbert_service:
                raise ValueError("ColbertService not initialized")
            self.colbert_service.delete_index()
            await self.db['knowledge_bases'].delete_one({'_id': ObjectId(kb_id)})
            await self.db['kb_docs'].delete_many({'kb_id': kb_id})
        except Exception as e:
            logging.error(f"Error deleting kb by id: {str(e)}")
            raise

    async def create_new_kb(self, uid, name, objective):
        try:
            kb_details = {
                'name': name,
                'index_path': None,
                'uid': uid,
                'objective': objective,
                'documents': [],
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            result = await self.db['knowledge_bases'].insert_one(kb_details)
            kb_id = str(result.inserted_id)
            kb_details['id'] = kb_id
            return kb_details
        except Exception as e:
            logging.error(f"Error creating new kb: {str(e)}")
            raise