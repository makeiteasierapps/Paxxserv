from bson import ObjectId
from bson.errors import InvalidId
from pymongo import UpdateOne
import logging
from app.utils.token_counter import token_counter

class KbDocumentService:
    def __init__(self, db, kb_id, colbert_service=None, openai_client=None):
        self.db = db
        self.kb_id = kb_id
        self.colbert_service = colbert_service
        self.openai_client = openai_client
    
    def set_colbert_service(self, colbert_service):
        self.colbert_service = colbert_service

    def set_openai_client(self, openai_client):
        self.openai_client = openai_client

    async def get_docs_by_kbId(self):
        try:
            docs_list = []
            async for doc in self.db['kb_docs'].find({'kb_id': self.kb_id}):
                doc_dict = {'id': str(doc['_id']), **doc}
                doc_dict.pop('_id', None)
                docs_list.append(doc_dict)
            return docs_list
        except Exception as e:
            logging.error(f"Error getting docs by kbId: {str(e)}")
            raise

    async def delete_doc_by_id(self, doc_id):
        try:
            doc = await self.db['kb_docs'].find_one({'_id': ObjectId(doc_id)})
            if doc:
                embedded_sources = [
                    url_doc['metadata']['sourceURL']
                    for url_doc in doc.get('content', [])
                    if url_doc.get('isEmbedded', False)
                ]
                
                await self.db['kb_docs'].delete_one({'_id': ObjectId(doc_id)})
                
                return embedded_sources
            else:
                logging.warning(f"Document with id {doc_id} not found")
                return []
        except InvalidId:
            logging.error(f"Invalid document ID: {doc_id}")
            raise
        except Exception as e:
            logging.error(f"Error deleting doc by id: {str(e)}")
            raise

    async def delete_page_by_source(self, doc_id, page_source):
        try:
            await self.db['kb_docs'].update_one(
                {'_id': ObjectId(doc_id)},
                {'$pull': {'content': {'metadata.sourceURL': page_source}}}
            )
        except Exception as e:
            logging.error(f"Error deleting page by source: {str(e)}")
            raise

    async def handle_doc_db_update(self, source, doc_type, content, doc_id=None, additional_data=None):
        try:
            kb_doc = {
                'type': doc_type,
                'kb_id': self.kb_id,
                'source': source,
                'content': content,
                'token_count': sum(url_doc.get('token_count', 0) for url_doc in content)
            }

            if additional_data:
                kb_doc.update(additional_data)

            if doc_id:
                result = await self.db['kb_docs'].update_one(
                    {'_id': ObjectId(doc_id)},
                    {'$set': kb_doc}
                )
                if result.matched_count > 0:
                    updated_doc = await self.db['kb_docs'].find_one({'_id': ObjectId(doc_id)})
                    updated_doc['id'] = str(updated_doc.pop('_id'))
                    return updated_doc
                else:
                    return 'not_found'
            else:
                result = await self.db['kb_docs'].insert_one(kb_doc)
                kb_doc['id'] = str(result.inserted_id)
                kb_doc.pop('_id', None)
                return kb_doc
        except Exception as e:
            logging.error(f"Error handling doc db update: {str(e)}")
            raise

    async def save_documents(self, documents, doc_id):
        try:
            update_list = []
            for page in documents:
                new_token_count = token_counter(page['content'])
                update_list.append({
                    'source': page['source'],
                    'update': {
                        'content.$.content': page['content'],
                        'content.$.token_count': new_token_count,
                        'content.$.isEmbedded': False
                    }
                })

            updated_doc = await self._bulk_update_document(doc_id, update_list)
            
            # Calculate and update the new total token count
            new_total_token_count = sum(page.get('token_count', 0) for page in updated_doc['content'])
            await self.db['kb_docs'].update_one(
                {'_id': ObjectId(doc_id)},
                {'$set': {'token_count': new_total_token_count}}
            )
            
            updated_doc['token_count'] = new_total_token_count
                
            return updated_doc
        except Exception as e:
            logging.error(f"Error saving documents: {str(e)}")
            raise

    async def embed_document(self, doc_id, specific_sources=None):
        if not self.colbert_service:
            raise ValueError("ColbertService not initialized")

        try:
            doc = await self.db['kb_docs'].find_one({'_id': ObjectId(doc_id)})
            if not doc:
                raise ValueError(f"Document with id {doc_id} not found")

            # Determine which content needs to be embedded
            content_to_embed = []
            for url_doc in doc['content']:
                if specific_sources is None:
                    # If no specific sources are provided, embed all non-embedded content
                    if not url_doc.get('isEmbedded', False):
                        content_to_embed.append(url_doc)
                elif url_doc['metadata']['sourceURL'] in specific_sources:
                    # If specific sources are provided, only embed those
                    content_to_embed.append(url_doc)

            if not content_to_embed:
                return doc  # Nothing to embed
        
            prepared_documents = [{'content': doc['content'], 'id': doc['metadata']['sourceURL']} for doc in content_to_embed if 'content' in doc and 'metadata' in doc and 'sourceURL' in doc['metadata']]
        
            result = self.colbert_service.process_content(prepared_documents)
            if 'index_path' in result:
                await self.update_knowledge_base(index_path=result['index_path'])
            else:
                logging.info(f"Documents added to existing index: {result['message']}")
            
            # Update the isEmbedded field for processed content
            update_list = [
                {
                    'source': url_doc['metadata']['sourceURL'],
                    'update': {'content.$.isEmbedded': True}
                }
                for url_doc in content_to_embed
            ]
            return await self._bulk_update_document(doc_id, update_list)
        except Exception as e:
            logging.error(f"Error embedding document: {str(e)}")
            raise

    async def generate_summaries(self, content):
        try:
            if not self.openai_client:
                raise ValueError("OpenAiClient not initialized")
        
            if isinstance(content, str):
                return [await self.openai_client.summarize_content(content)]
            elif isinstance(content, list):
                return [await self.openai_client.summarize_content(url['content']) for url in content]
            else:
                return []
        except Exception as e:
            logging.error(f"Error generating summaries: {str(e)}")
            raise
    
    async def _bulk_update_document(self, doc_id, update_list):
        try:
            update_operations = [
                UpdateOne(
                    {
                        '_id': ObjectId(doc_id),
                        'content.metadata.sourceURL': item['source']
                    },
                    {
                        '$set': item['update']
                    }
                ) for item in update_list
            ]

            result = await self.db['kb_docs'].bulk_write(update_operations)
            
            if result.modified_count == 0:
                raise ValueError(f"Failed to update document with id {doc_id}")
            
            updated_doc = await self.db['kb_docs'].find_one({'_id': ObjectId(doc_id)})
            updated_doc['id'] = str(updated_doc.pop('_id'))
            
            return updated_doc
        except Exception as e:
            logging.error(f"Error bulk updating document: {str(e)}")
            raise

    # Add this method to the KbDocumentService class
    async def is_document_embedded(self, doc_id, page_source):
        try:
            result = await self.db['kb_docs'].find_one(
                {'_id': ObjectId(doc_id), 'content.metadata.sourceURL': page_source},
                {'content.$': 1}
            )
            if result and 'content' in result and len(result['content']) > 0:
                return result['content'][0].get('isEmbedded', False)
            return False
        except Exception as e:
            logging.error(f"Error checking if document is embedded: {str(e)}")
            return False
    
    async def update_knowledge_base(self, **kwargs):
        try:
            knowledge_base = await self.db['knowledge_bases'].find_one({'_id': ObjectId(self.kb_id)})
            if knowledge_base:
                await self.db['knowledge_bases'].update_one({'_id': ObjectId(self.kb_id)}, {'$set': kwargs})
                return 'knowledge base updated'
            else:
                return 'knowledge base not found'
        except Exception as e:
            logging.error(f"Error updating knowledge base: {str(e)}")
            raise