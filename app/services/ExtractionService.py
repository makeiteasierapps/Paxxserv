import os
import time
import pymupdf4llm
import fitz
import requests
from dotenv import load_dotenv
from fastapi import HTTPException
from app.utils.token_counter import token_counter
from app.services.LocalStorageService import LocalStorageService

load_dotenv()

class ExtractionService:
    def __init__(self, db, uid):
        self.db = db
        self.uid = uid
        self.local_storage = LocalStorageService()

    async def extract_from_pdf(self, file, kb_id, kb_services):
        try:
            file_content = await file.read()
            pdf_document = fitz.open(stream=file_content, filetype="pdf")
            md_text = pymupdf4llm.to_markdown(pdf_document)
            cleaned_source = file.filename
            kb_doc = kb_services.create_kb_doc_in_db(kb_id, cleaned_source, 'pdf', content=md_text)
            pdf_document.close()

            return kb_doc

        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            raise HTTPException(status_code=500, detail="Failed to extract text from PDF")

    def extract_from_url(self, url, endpoint, kb_services):
        normalized_url = self.normalize_url(url)
        firecrawl_url = os.getenv('FIRECRAWL_DEV_URL') if os.getenv('LOCAL_DEV') == 'true' else os.getenv('FIRECRAWL_URL')
        params = {
            'url': normalized_url,
            'pageOptions': {
                'onlyMainContent': True,
            },
        }
        
        try:
            firecrawl_response = requests.post(f"{firecrawl_url}/{endpoint}", json=params, timeout=60)
            firecrawl_response.raise_for_status()
            firecrawl_data = firecrawl_response.json()

            if 'jobId' in firecrawl_data:
                content = self.poll_job_status(firecrawl_url, firecrawl_data['jobId'])
            else:
                content = [{
                    'markdown': firecrawl_data['data']['markdown'],
                    'metadata': firecrawl_data['data']['metadata'],
                }]
            
            url_docs = [{
                'content': url_content.get('markdown'),
                'token_count': token_counter(url_content.get('markdown')),
                'metadata': url_content.get('metadata')
            } for url_content in content]

            kb_doc = kb_services.handle_doc_db_update(normalized_url, 'url', content=url_docs)
            return kb_doc

        except requests.RequestException as e:
            print(f"Error crawling site: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to crawl site: {str(e)}")

    def poll_job_status(self, firecrawl_url, job_id):
        while True:
            status_response = requests.get(f"{firecrawl_url}/crawl/status/{job_id}", timeout=10)
            status_response.raise_for_status()
            status_data = status_response.json()
            
            if status_data['status'] == 'completed':
                return status_data['data']
            elif status_data['status'] == 'failed':
                raise Exception(f"Crawl job {job_id} failed")
            
            time.sleep(5)

    def normalize_url(self, url):
        url = url.lower()
        if url.startswith("http://"):
            url = url[7:]
        elif url.startswith("https://"):
            url = url[8:]
        url = url.split('#')[0]
        url = url.split('?')[0]  
        if url.endswith('/'):
            url = url[:-1]
        return url
    
    def parse_extraction_response(self, response):
        for url_content in response[0]['urls']:
            content = url_content['content']
            token_count = url_content['token_count']
            source_url = url_content['metadata']['sourceURL']

        return {
            'content': content,
            'token_count': token_count,
            'source_url': source_url
        }