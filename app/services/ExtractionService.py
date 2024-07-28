import os
import time
import json
import requests
from flask import jsonify
from canopy.tokenizer import Tokenizer
from app.services.FirebaseStoreageService import FirebaseStorageService as firebase_storage

Tokenizer.initialize()
tokenizer = Tokenizer()
class ExtractionService:
    def __init__(self, db, uid):
        self.db = db
        self.uid = uid

    def extract_from_pdf(self, file, kb_id, uid, kb_services):
        firecrawl_url = os.getenv('FIRECRAWL_URL')
        headers = {'api': os.getenv('PAXXSERV_API')}

        try:
            pdf_url = firebase_storage.upload_file(file, uid, 'documents')
            payload = {'url': pdf_url}
            response = requests.post(f"{firecrawl_url}/scrape", json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            response_data = response.json()
            content = response_data['data']['content']
            source = response_data['data']['metadata']['sourceURL']
            cleaned_source = os.path.basename(source)
            kb_doc = kb_services.create_kb_doc_in_db(kb_id, cleaned_source, 'pdf', content=content)
            return jsonify(kb_doc), 200
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return jsonify({'message': 'Failed to extract text from PDF'}), 500

    def extract_from_url(self, normalized_url, kb_id, endpoint, kb_services):
        firecrawl_url = os.getenv('FIRECRAWL_URL')
        params = {
            'url': normalized_url,
            'pageOptions': {
                'onlyMainContent': True,
            },
        }
        headers = {'api': os.getenv('PAXXSERV_API')}
        
        try:
            firecrawl_response = requests.post(f"{firecrawl_url}/{endpoint}", json=params, headers=headers, timeout=10)
            if not firecrawl_response.ok:
                yield f'{{"status": "error", "message": "Failed to scrape url"}}'
                return

            firecrawl_data = firecrawl_response.json()
            yield f'{{"status": "started", "message": "Crawl job started"}}'

            if 'jobId' in firecrawl_data:
                content = self.poll_job_status(firecrawl_url, firecrawl_data['jobId'], headers)
            else:
                content = [{
                    'markdown': firecrawl_data['data']['markdown'],
                    'metadata': firecrawl_data['data']['metadata'],
                }]
            
            url_docs = []
            for url_content in content:
                metadata = url_content.get('metadata')
                markdown = url_content.get('markdown')
                source_url = metadata.get('sourceURL')
                url_docs.append({
                    'content': markdown,
                    'token_count': tokenizer.token_count(markdown),
                    'metadata': metadata
                })
                yield f'{{"status": "processing", "message": "Processing {source_url}"}}'

            kb_doc = kb_services.create_kb_doc_in_db(kb_id, normalized_url, 'url', urls=url_docs)
            
            yield f'{{"status": "completed", "content": {json.dumps(kb_doc, ensure_ascii=False)}}}'

        except Exception as e:
            print(f"Error crawling site: {e}")
            yield f'{{"status": "error", "message": "Failed to crawl site: {str(e)}"}}'

    def poll_job_status(self, firecrawl_url, job_id, headers):
        while True:
            status_response = requests.get(f"{firecrawl_url}/crawl/status/{job_id}", headers=headers, timeout=10)
            status_response.raise_for_status()
            status_data = status_response.json()
            
            if status_data['status'] == 'completed':
                return status_data['data']
            elif status_data['status'] == 'failed':
                raise Exception(f"Crawl job {job_id} failed")
            
            time.sleep(5)
