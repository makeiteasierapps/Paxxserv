# Seperate out the document logic into its own service file. 

import os
from bson import ObjectId
from datetime import datetime
from dotenv import load_dotenv
from canopy.tokenizer import Tokenizer
from app.agents.DocumentManager import DocumentManager

load_dotenv()
Tokenizer.initialize()
tokenizer = Tokenizer()

class KnowledgeBaseService:
    def __init__(self, db, uid):
        self.document_manager = DocumentManager(db, uid)
        self.db = db
        self.uid = uid

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
                'uid': uid,
                'objective': objective,
                'documents': [],
                'urls': [],
                'created_at': datetime.utcnow()
            }
        new_kb = self.db['knowledge_bases'].insert_one(kb_details)
        # Convert the '_id' to 'id' and remove '_id' from the dictionary
        kb_id = str(new_kb.inserted_id)
        kb_details['id'] = kb_id
        del kb_details['_id']

        return kb_details

    def create_chunks_and_embeddings(self, source, content, highlights=None):
        chunks = self.document_manager.chunkify(source=source, content=content, highlights=highlights)
        chunks_with_embeddings = self.document_manager.embed_chunks(chunks)
        return chunks_with_embeddings
    
    def create_kb_doc_in_db(self, kb_id, content, source, doc_type, highlights=None, doc_id=None):
        kb_doc = {
            'type': doc_type,
            'chunks': [],
            'content': content,
            'kb_id': kb_id,
            'token_count': tokenizer.token_count(content),
            'source': source,
        }
        if highlights:
            kb_doc['highlights'] = highlights

        if doc_id:
            result = self.db['kb_docs'].update_one({'_id': ObjectId(doc_id)}, {'$set': kb_doc})
            if result.matched_count > 0:
                kb_doc['id'] = doc_id
            else:
                return 'not_found'
        else:
            result = self.db['kb_docs'].insert_one(kb_doc)
            kb_doc['id'] = str(result.inserted_id)

        kb_doc.pop('_id', None)
        return kb_doc
    
    def chunk_and_embed_content(self, content, source, kb_id, doc_id, highlights=None):
        # Check if the document has existing chunks and delete them
        existing_doc = self.db['kb_docs'].find_one({'_id': ObjectId(doc_id)})
        if existing_doc and 'chunks' in existing_doc:
            self.db['chunks'].delete_many({'_id': {'$in': existing_doc['chunks']}})

        chunks_with_embeddings = self.create_chunks_and_embeddings(source, content, highlights)
        content_summary = self.document_manager.summarize_content(content)
        
        chunk_ids = []
        for chunk in chunks_with_embeddings:
            metadata_text = chunk['metadata']['text']
            metadata_source = chunk['metadata']['source']
            chunk_to_insert = {
                **chunk,
                'text': metadata_text,
                'source': metadata_source,
                'doc_id': str(doc_id),
                'kb_id': kb_id,
                'summary': content_summary
            }
            chunk_to_insert.pop('metadata', None)
            chunk_to_insert.pop('id', None)
            inserted_chunk = self.db['chunks'].insert_one(chunk_to_insert)
            chunk_ids.append(inserted_chunk.inserted_id)

        self.db['kb_docs'].update_one({'_id': ObjectId(doc_id)}, {'$set': {'chunks': chunk_ids, 'summary': content_summary}})

        updated_doc = self.db['kb_docs'].find_one({'_id': ObjectId(doc_id)})
        
        if '_id' in updated_doc:
            updated_doc['id'] = str(updated_doc['_id'])
            updated_doc.pop('_id', None)
        if 'chunks' in updated_doc:
            updated_doc['chunks'] = [str(chunk_id) for chunk_id in updated_doc['chunks']]
        
        return updated_doc
        
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

    def save_embed_pdf(self, data, kb_id):
        try:
            content = data['content']
            source = data['metadata']['sourceURL']
            cleaned_source = os.path.basename(source)
            chunks_with_embeddings = self.create_chunks_and_embeddings(cleaned_source, content)
            kb_doc = self.create_kb_doc_in_db(kb_id, content, cleaned_source, 'pdf')
            doc_id = kb_doc['id']

            # Now, insert each chunk with the doc_id included
            chunk_ids = []
            for chunk in chunks_with_embeddings:
                # Unpack the metadata to extract 'content' and 'source' directly
                metadata_text = chunk['metadata']['text']
                metadata_source = chunk['metadata']['source']
                # Prepare the chunk without the 'metadata' field but with 'content' and 'source' directly
                chunk_to_insert = {
                    **chunk,
                    'content': metadata_text,
                    'source': metadata_source,
                    'doc_id': doc_id
                }
                # Remove the original 'metadata'/ id fields
                chunk_to_insert.pop('metadata', None)
                chunk_to_insert.pop('id', None)
                try:
                    inserted_chunk = self.db['chunks'].insert_one(chunk_to_insert)
                    chunk_ids.append(inserted_chunk.inserted_id)
                except Exception as chunk_error:
                    print(f"Error inserting chunk: {chunk_to_insert}, Error: {chunk_error}")

            # Finally, update the kb_doc with the list of chunk_ids
            self.db['kb_docs'].update_one({'_id': doc_id}, {'$set': {'chunks': chunk_ids}})
            return content

        except Exception as e:
            print(f"Error in save_embed_pdf: {e}")
            return None 
    