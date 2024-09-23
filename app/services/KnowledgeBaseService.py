from bson import ObjectId
from datetime import datetime, UTC
from dotenv import load_dotenv
from app.utils.token_counter import token_counter
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
        kb = self.db['knowledge_bases'].find_one({'_id': ObjectId(self.kb_id)})
        return kb['index_path'] if kb else None
    
    def process_colbert_content(self, content, source):
        if not self.colbert_service:
            raise ValueError("ColbertService not initialized")
        
        if self.index_path is None:
            results = self.colbert_service.process_content(None, content, source)
            new_index_path = results['index_path']
            self.update_knowledge_base(index_path=new_index_path)
            return {'index_path': new_index_path, 'created': True}
        else:
            status = self.colbert_service.process_content(self.index_path, content, source)
            return {'status': status, 'created': False}

    def get_kb_list(self, uid):
        kb_list_cursor = self.db['knowledge_bases'].find({'uid': uid})
        kb_list = [{'id': str(kb['_id']), **kb} for kb in kb_list_cursor]
        for kb in kb_list:
            kb.pop('_id', None)
        return kb_list
    
    def get_docs_by_kbId(self):
        docs_cursor = self.db['kb_docs'].find({'kb_id': self.kb_id})
        docs_list = [{'id': str(doc['_id']), **doc} for doc in docs_cursor]
        for doc in docs_list:
            if 'chunks' in doc:
                doc['chunks'] = [str(chunk_id) for chunk_id in doc['chunks']]
            doc.pop('_id', None)
        return docs_list
    
    def delete_kb_by_id(self, kb_id):
        if not self.colbert_service:
            raise ValueError("ColbertService not initialized")
        self.colbert_service.delete_index(self.index_path)
        self.db['knowledge_bases'].delete_one({'_id': ObjectId(kb_id)})
        self.db['kb_docs'].delete_many({'kb_id': kb_id})
        
    def delete_doc_by_id(self, doc_id):
        if not self.colbert_service:
            raise ValueError("ColbertService not initialized")
        
        self.db['kb_docs'].delete_one({'_id': ObjectId(doc_id)})
        self.db['chunks'].delete_many({'doc_id': doc_id})
        self.colbert_service.delete_document_from_index(doc_id)
    
    def create_new_kb(self, uid, name, objective):
        kb_details = {
                'name': name,
                'index_path': None,
                'uid': uid,
                'objective': objective,
                'documents': [],
                'created_at': datetime.now(UTC)
            }
        new_kb = self.db['knowledge_bases'].insert_one(kb_details)
        kb_id = str(new_kb.inserted_id)
        kb_details['id'] = kb_id
        del kb_details['_id']
        return kb_details
 
    def update_knowledge_base(self, **kwargs):
        knowledge_base = self.db['knowledge_bases'].find_one({'_id': ObjectId(self.kb_id)})
        if knowledge_base:
            self.db['knowledge_bases'].update_one({'_id': ObjectId(self.kb_id)}, {'$set': kwargs})
            return 'knowledge base updated'
        else:
            return 'knowledge base not found'

    def generate_summaries(self, content):
        if not self.openai_client:
            raise ValueError("OpenAiClient not initialized")
        
        if isinstance(content, str):
            return [self.openai_client.summarize_content(content)]
        elif isinstance(content, list):
            return [self.openai_client.summarize_content(url['content']) for url in content]
        else:
            return []

    def update_kb_document(self, source, doc_type, content, summaries, doc_id=None):
        update_data = {}
        if isinstance(content, str):
            update_data['summary'] = summaries[0]
        else:
            update_data['content'] = [
                {**url, 'summary': summary}
                for url, summary in zip(content, summaries)
            ]

        return self.handle_doc_db_update(source, doc_type, content, doc_id, update_data)
    
    def handle_doc_db_update(self, source, doc_type, content, doc_id=None, additional_data=None):
        if not self.kb_id:
            raise ValueError("kb_id not set")
        
        kb_doc = {
            'type': doc_type,
            'kb_id': self.kb_id,
            'source': source,
        }
        
        if isinstance(content, str):
            kb_doc['content'] = content
            kb_doc['token_count'] = token_counter(content)
        elif isinstance(content, list):
            kb_doc['content'] = content
            kb_doc['token_count'] = sum(url_doc.get('token_count', 0) for url_doc in content)
        else:
            kb_doc['content'] = ''
            kb_doc['token_count'] = 0

        if additional_data:
            kb_doc.update(additional_data)

        if doc_id:
            result = self.db['kb_docs'].update_one(
                {'_id': ObjectId(doc_id)},
                {'$set': kb_doc}
            )
            if result.matched_count > 0:
                updated_doc = self.db['kb_docs'].find_one({'_id': ObjectId(doc_id)})
                updated_doc['id'] = str(updated_doc.pop('_id'))
                if 'chunks' in updated_doc:
                    updated_doc['chunks'] = [str(chunk_id) for chunk_id in updated_doc['chunks']]
                return updated_doc
            else:
                return 'not_found'
        else:
            result = self.db['kb_docs'].insert_one(kb_doc)
            kb_doc['id'] = str(result.inserted_id)
            kb_doc.pop('_id', None)
            return kb_doc