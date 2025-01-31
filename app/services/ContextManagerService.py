from typing import List, Dict, Any, Optional
import base64
import os
from app.services.interfaces import ExtractionProvider, SettingsProvider
from dotenv import load_dotenv
import logging
load_dotenv()

class ContextManagerService:
    def __init__(
        self,
        extraction_provider: ExtractionProvider,
        settings_provider: Optional[SettingsProvider] = None
    ):
        self.extraction_provider = extraction_provider
        self.settings_provider = settings_provider

    def prepare_url_content(self, url_contents: List[Dict[str, Any]]) -> str:
        combined_content = "<<URL_CONTENT_START>>\n"
        combined_content += "Answer the users question using the content from the following urls:\n"
        
        for url_data in url_contents:
            combined_content += f"URL: {url_data['source']}\n"
            combined_content += f"CONTENT: {url_data['content']}\n\n"
        
        combined_content += "<<URL_CONTENT_END>>"
        return combined_content

    async def process_context(self, context: List[Dict[str, Any]], user_message: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Main method to process all types of context and combine results
        """
        url_context = [item for item in context if item.get('type') == 'url'] or None
        image_context = [item for item in context if item.get('type') == 'image'] or None
        kb_context = [item for item in context if item.get('type') == 'kb'] or None
        file_context = [item for item in context if item.get('type') == 'file'] or None
        results = {}

        if url_context:
            prepared_url_content, url_contents = await self.process_url_context(url_context)
            results['url'] = prepared_url_content
            if self.settings_provider:
                # Create a lookup dictionary for quick source-to-content mapping
                content_updates = {item['source']: item['content'] for item in url_contents}
                
                # Update the content in the original context list
                for item in context:
                    if item.get('source') in content_updates:
                        item['content'] = content_updates[item['source']]
                
                # Update the entire context array
                await self.settings_provider.update_settings(context=context)
        
        if file_context:
            results['file'] = self.process_file_context(file_context)
        
        if image_context:
            results['image'] = await self.process_image_context(image_context, user_message)
        
        if kb_context and user_message:
            results['kb'] = await self.process_kb_context(kb_context, user_message)

        return self.combine_context_results(results)

    async def process_url_context(self, url_context: List[Dict[str, Any]]) -> str:
        """
        Process URL type context using extraction provider
        """
        url_contents = []
        urls_to_extract = []
        
        for url_item in url_context:
            if 'content' in url_item and url_item['content']:
                url_contents.append(url_item)
            else:
                urls_to_extract.append(url_item['source'])

        if urls_to_extract:
            for url in urls_to_extract:
                extracted_docs = []
                for result in await self.extraction_provider.extract_from_url(url, 'scrape', False):
                    extracted_docs.append(result)
                    
                if extracted_docs:
                    docs_response = self.extraction_provider.parse_extraction_response(extracted_docs)
                    url_contents.append({
                        'source': url,
                        'content': docs_response['content'],
                    })

        return self.prepare_url_content(url_contents), url_contents

    async def process_image_context(self, image_context: List[Dict[str, Any]], user_message: dict) -> dict:
        """
        Takes image context and user message dict and returns the updated user message with images array
        """
        is_local = os.getenv('LOCAL_DEV') == 'true'
        base_path = '/mnt/media_storage' if not is_local else os.path.join(os.getcwd(), 'media_storage')
        image_urls = []
        for image in image_context:
            file_path = image.get('image_path')
            full_path = os.path.join(base_path, file_path)
            if file_path and os.path.exists(full_path):
                with open(full_path, 'rb') as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                    image_urls.append({
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    })
        user_message['images'] = image_urls
        return user_message

    async def process_kb_context(self, kb_context: List[Dict[str, Any]], user_message: str) -> List[Dict[str, Any]]:
        """
        Process knowledge base type context using ColbertService
        """
        kb_results = []
        
        # for kb_item in kb_context:
        #     kb_id = kb_item.get('kb_id')
        #     if kb_id:
        #         kb_service = KnowledgeBaseService(self.db, self.uid, kb_id)
        #         colbert_service = ColbertService(kb_service.index_path)
        #         search_results = colbert_service.search_index(user_message)
        #         kb_results.append({
        #             'kb_id': kb_id,
        #             'content': colbert_service.prepare_vector_response(search_results),
        #             'type': 'kb'
        #         })
        
        return kb_results

    def process_file_context(self, file_context: List[Dict[str, Any]]) -> str:
        """
        Process file context into a formatted string
        """
        return ''.join([f"# {item['path']}\n{item['content']}\n" for item in file_context])

    def combine_context_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Combine all context results into a final format
        """
        system_context = []
        user_message = None
        try:
            if 'url' in results:
                system_context.append(results['url'])
                
            if 'kb' in results:
                for kb_result in results['kb']:
                    system_context.append(kb_result['content'])
            
            if 'image' in results:
                user_message = results['image']

            if 'file' in results:
                system_context.append(results['file'])
                
            response = {}
            if system_context:
                response['system_context'] = '\n\n'.join(system_context)
            if user_message:
                response['user_message'] = user_message
        except Exception as e:
            logging.error('Error combining context results: %s', str(e))
            response = {}

        return response