import time
from bson import ObjectId
from datetime import datetime
from dotenv import load_dotenv
from canopy.tokenizer import Tokenizer
from app.agents.DocumentManager import DocumentManager

load_dotenv()
Tokenizer.initialize()
tokenizer = Tokenizer()

class ProjectService:
    def __init__(self, db, uid):
        self.document_manager = DocumentManager(db, uid)
        self.db = db
        self.uid = uid

    def get_projects(self, uid):
        projects_cursor = self.db['projects'].find({'uid': uid})
        project_list = [{'id': str(project['_id']), **project} for project in projects_cursor]
        for project in project_list:
            project.pop('_id', None)
        return project_list
    
    def get_docs_by_projectId(self, project_id):
        docs_cursor = self.db['project_docs'].find({'project_id': project_id})
        docs_list = [{'id': str(doc['_id']), **doc} for doc in docs_cursor]
        for doc in docs_list:
            if 'chunks' in doc:
                doc['chunks'] = [str(chunk_id) for chunk_id in doc['chunks']]
            doc.pop('_id', None)
        return docs_list
    
    def delete_project_by_id(self, project_id):
        self.db['projects'].delete_one({'_id': ObjectId(project_id)})
        self.db['project_docs'].delete_many({'project_id': project_id})
        self.db['chunks'].delete_many({'project_id': project_id})
        self.db['chats'].delete_one({'project_id': project_id})
        
    def delete_doc_by_id(self, doc_id):
        self.db['project_docs'].delete_one({'_id': ObjectId(doc_id)})
        self.db['chunks'].delete_many({'doc_id': doc_id})

    def chunk_embed_url(self, content, url, project_id):
        chunks = self.document_manager.chunkify(url, content)
        chunks_with_embeddings = self.document_manager.embed_chunks(chunks)
        content_summary = self.document_manager.summarize_content(content)
        normalized_url = self.normalize_url(url)

        project_doc = {
            'type': 'url',
            'chunks': [],
            'content': content,
            'project_id': project_id,
            'token_count': tokenizer.token_count(content),
            'source': normalized_url,
            'summary': content_summary
        }
        
        inserted_doc = self.db['project_docs'].insert_one(project_doc)
        doc_id = inserted_doc.inserted_id

        chunk_ids = []
        for chunk in chunks_with_embeddings:
            metadata_text = chunk['metadata']['text']
            metadata_source = chunk['metadata']['source']
            chunk_to_insert = {
                **chunk,
                'text': metadata_text,
                'source': metadata_source,
                'doc_id': str(doc_id),
                'project_id': project_id
            }
            chunk_to_insert.pop('metadata', None)
            chunk_to_insert.pop('id', None)
            inserted_chunk = self.db['chunks'].insert_one(chunk_to_insert)
            chunk_ids.append(inserted_chunk.inserted_id)

        self.db['project_docs'].update_one({'_id': doc_id}, {'$set': {'chunks': chunk_ids}})

        updated_doc = self.db['project_docs'].find_one({'_id': doc_id})
        
        if '_id' in updated_doc:
            updated_doc['id'] = str(updated_doc['_id'])
            updated_doc.pop('_id', None)
        if 'chunks' in updated_doc:
            updated_doc['chunks'] = [str(chunk_id) for chunk_id in updated_doc['chunks']]
        
    def normalize_url(self, url):
        # Example normalization process
        url = url.lower()
        if url.startswith("http://"):
            url = url[7:]
        elif url.startswith("https://"):
            url = url[8:]
        url = url.split('#')[0]  # Remove fragment
        url = url.split('?')[0]  # Remove query
        if url.endswith('/'):
            url = url[:-1]
        return url

    def extract_pdf(self, file, project_id):
        text = 'placeholder'
        num_tokens = tokenizer.token_count(text)

        file_name = file.filename

        # Chunkify the extracted text
        chunks = self.document_manager.chunkify(text, file_name)
        # Embed the chunks
        embeddings = self.document_manager.embed_chunks(chunks)

        # Insert the project_doc without the chunks to get the doc_id
        project_doc = {
            'type': 'pdf',
            'chunks': [],  # Temporarily leave this empty
            'value': text,
            'project_id': project_id,
            'token_count': num_tokens,
            'source': file_name
        }
        inserted_doc = self.db['project_docs'].insert_one(project_doc)
        doc_id = inserted_doc.inserted_id

        # Now, insert each chunk with the doc_id included
        chunk_ids = []
        for chunk in embeddings:
            # Unpack the metadata to extract 'text' and 'source' directly
            metadata_text = chunk['metadata']['text']
            metadata_source = chunk['metadata']['source']
            # Prepare the chunk without the 'metadata' field but with 'text' and 'source' directly
            chunk_to_insert = {
                **chunk,
                'text': metadata_text,
                'source': metadata_source,
                'doc_id': doc_id
            }
            # Remove the original 'metadata'/ id fields
            chunk_to_insert.pop('metadata', None)
            chunk_to_insert.pop('id', None)
            inserted_chunk = self.db['chunks'].insert_one(chunk_to_insert)
            chunk_ids.append(inserted_chunk.inserted_id)

        # Finally, update the project_doc with the list of chunk_ids
        self.db['project_docs'].update_one({'_id': doc_id}, {'$set': {'chunks': chunk_ids}})
        return text

    def create_new_project(self, uid, name, objective):
        project_details = {
                'name': name,
                'uid': uid,
                'objective': objective,
                'documents': [],
                'urls': [],
                'created_at': datetime.utcnow()
            }
        new_project = self.db['projects'].insert_one(project_details)
        # Convert the '_id' to 'id' and remove '_id' from the dictionary
        project_id = str(new_project.inserted_id)
        project_details['id'] = project_id
        del project_details['_id']

        new_chat = {
            'uid': uid,
            'chat_name': name,
            'agent_model': 'GPT-4',
            'system_prompt': '',
            'chat_constants': '',
            'use_profile_data': False,
            'is_open': False,
            'project_id': project_id, 
            'created_at': datetime.utcnow()
        }

        # Let MongoDB generate the chat_id
        result = self.db['chats'].insert_one(new_chat)
        new_chat['chatId'] = str(result.inserted_id)
        del new_chat['_id']

        return project_details, new_chat

    def save_text_doc(self, project_id, text, highlights=None, doc_id=None, category=None):
        new_doc = {
            'project_id': project_id,
            'content': text,
            'category': category,
            'highlights': highlights,
            'type': 'text'
        }
        if doc_id:
            result = self.db['project_docs'].update_one({'_id': ObjectId(doc_id)}, {'$set': new_doc})
            if result.matched_count > 0:
                return doc_id
            else:
                return 'not_found'
        else:
            result = self.db['project_docs'].insert_one(new_doc)
            new_doc_id = str(result.inserted_id)
            return new_doc_id

    def get_text_docs(self, project_id):
        docs_cursor = self.db['project_docs'].find({'project_id': project_id, 'type': 'text'})
        docs_list = []
        for doc in docs_cursor:
            doc['id'] = str(doc['_id'])
            doc.pop('_id', None)
            doc.pop('chunks', None)
            docs_list.append(doc)
        if docs_list:
            return docs_list
        else:
            return []
        
    def embed_text_doc(self, doc_id, project_id, doc, highlights, category):
        # Check if the document has existing chunks and delete them
        existing_doc = self.db['project_docs'].find_one({'_id': ObjectId(doc_id)})
        if existing_doc and 'chunks' in existing_doc:
            self.db['chunks'].delete_many({'_id': {'$in': existing_doc['chunks']}})
        updated_highlights = [{**highlight, 'id': doc_id} for highlight in highlights]
        chunks = self.document_manager.chunkify(chunks=updated_highlights, source='user')
        chunks_with_embeddings = self.document_manager.embed_chunks(chunks)
        content_summary = self.document_manager.summarize_content(doc)
        
        chunk_ids = []
        for chunk in chunks_with_embeddings:
            metadata_text = chunk['metadata']['text']
            metadata_source = chunk['metadata']['source']
            chunk_to_insert = {
                **chunk,
                'text': metadata_text,
                'source': metadata_source,
                'category': category,
                'summary': content_summary,
                'doc_id': doc_id,
                'project_id': project_id
            }
            chunk_to_insert.pop('metadata', None)
            chunk_to_insert.pop('id', None)
            inserted_chunk = self.db['chunks'].insert_one(chunk_to_insert)
            chunk_ids.append(inserted_chunk.inserted_id)

        self.db['project_docs'].update_one({'_id': ObjectId(doc_id)}, {'$set': {'chunks': chunk_ids}})

        return chunks_with_embeddings