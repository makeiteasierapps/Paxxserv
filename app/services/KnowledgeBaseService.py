from bson import ObjectId
from datetime import datetime, UTC
from dotenv import load_dotenv
from app.utils.token_counter import token_counter
from app.services.ColbertService import ColbertService
from app.agents.OpenAiClient import OpenAiClient
load_dotenv()

class KnowledgeBaseService:
    def __init__(self, db, uid):
        self.colbert_service = ColbertService()
        self.openai_client = OpenAiClient(db, uid)
        self.db = db
        self.uid = uid
        self.index_path = None

    def get_kb_list(self, uid):
        kb_list_cursor = self.db['knowledge_bases'].find({'uid': uid})
        kb_list = [{'id': str(kb['_id']), **kb} for kb in kb_list_cursor]
        for kb in kb_list:
            kb.pop('_id', None)
        return kb_list
    
    def get_docs_by_kbId(self, kb_id):
        docs_cursor = self.db['kb_docs'].find({'kb_id': kb_id})
        docs_list = [{'id': str(doc['_id']), **doc} for doc in docs_cursor]
        for doc in docs_list:
            if 'chunks' in doc:
                doc['chunks'] = [str(chunk_id) for chunk_id in doc['chunks']]
            doc.pop('_id', None)
        return docs_list
    
    def delete_kb_by_id(self, kb_id):
        self.db['knowledge_bases'].delete_one({'_id': ObjectId(kb_id)})
        self.db['kb_docs'].delete_many({'kb_id': kb_id})
        self.db['chunks'].delete_many({'kb_id': kb_id})
        
    def delete_doc_by_id(self, doc_id):
        self.db['kb_docs'].delete_one({'_id': ObjectId(doc_id)})
        self.db['chunks'].delete_many({'doc_id': doc_id})

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
        # Convert the '_id' to 'id' and remove '_id' from the dictionary
        kb_id = str(new_kb.inserted_id)
        kb_details['id'] = kb_id
        del kb_details['_id']

        return kb_details
    
    def update_knowledge_base(self, kb_id, **kwargs):
        knowledge_base = self.db['knowledge_bases'].find_one({'_id': ObjectId(kb_id)})
        if knowledge_base:
            self.db['knowledge_bases'].update_one({'_id': ObjectId(kb_id)}, {'$set': kwargs})
            return 'knowledge base updated'
        else:
            return 'knowledge base not found'
        
    def process_colbert_content(self, kb_path, content):
        if kb_path is None:
            self.index_path = self.colbert_service.process_content(None, content)
            return {'index_path': self.index_path}
        else:
            self.index_path = kb_path
            status = self.colbert_service.process_content(self.index_path, content)
        return {'status': status}

    def generate_summaries(self, content):
        if isinstance(content, str):
            return [self.openai_client.summarize_content(content)]
        elif isinstance(content, list):
            return [self.openai_client.summarize_content(url['content']) for url in content]
        else:
            return []

    def update_kb_document(self, kb_id, source, doc_type, content, summaries, doc_id=None):
        update_data = {}
        if isinstance(content, str):
            update_data['summary'] = summaries[0]
        else:
            update_data['urls'] = [
                {**url, 'summary': summary}
                for url, summary in zip(content, summaries)
            ]

        return self.handle_doc_db_update(kb_id, source, doc_type, content, doc_id, update_data)

    def get_index_path(self, kb_id):
        kb = self.db['knowledge_bases'].find_one({'_id': ObjectId(kb_id)})
        return kb['index_path']
    
    def handle_doc_db_update(self, kb_id, source, doc_type, content, doc_id=None, additional_data=None):
        kb_doc = {
            'type': doc_type,
            'kb_id': kb_id,
            'source': source,
        }
        
        if isinstance(content, str):
            kb_doc['content'] = content
            kb_doc['token_count'] = token_counter(content)
        elif isinstance(content, list):
            kb_doc['urls'] = content
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