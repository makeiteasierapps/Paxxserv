from flask import Blueprint, Response, stream_with_context
import requests
import os
import time
import json
from dotenv import load_dotenv
from flask import jsonify, request, g
from app.services.KnowledgeBaseService import KnowledgeBaseService
from app.services.MongoDbClient import MongoDbClient
from app.services.FirebaseStoreageService import FirebaseStorageService as firebase_storage

load_dotenv()

kb_bp = Blueprint('kb_bp', __name__)

@kb_bp.before_request
def initialize_services():
    if request.method == "OPTIONS":
        return ("", 204)
    db_name = request.headers.get('dbName')
    g.uid = request.headers.get('uid')
    g.mongo_client = MongoDbClient(db_name)
    db = g.mongo_client.connect()
    g.kb_services = KnowledgeBaseService(db, g.uid)

@kb_bp.after_request
def close_mongo_connection(response):
    if hasattr(g, 'mongo_client'):
        g.mongo_client.close()
    return response

@kb_bp.route('/kb', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@kb_bp.route('/kb/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def kb(subpath):
    if request.method == "GET" and subpath == '':
        kb_list = g.kb_services.get_kb_list(g.uid)
        return jsonify({'kb_list': kb_list}), 200
    
    if request.method == "POST" and subpath == '':
        data = request.get_json()
        name = data.get('name')
        objective = data.get('objective')
        
        new_kb_details = g.kb_services.create_new_kb(g.uid, name, objective)
        return jsonify({'new_kb': new_kb_details}), 200
    
    if request.method == "DELETE" and subpath == '':
        data = request.get_json()
        kb_id = data.get('kbId')
        if not kb_id:
            return jsonify({'message': 'KB ID is required'}), 400
        g.kb_services.delete_kb_by_id(kb_id)
        return jsonify({'message': 'KB deleted'}), 200
    
    if subpath == "extract_pdf":
        firecrawl_url = os.getenv('FIRECRAWL_URL')
        file = request.files.get('file')
    
        if not file:
            return jsonify({'message': 'No file part'}), 400

        # Check if the file is a PDF
        if not file.filename.endswith('.pdf'):
            return jsonify({'message': 'File is not a PDF'}), 400
        
        kb_id = request.form.get('kbId')
        headers = {'api': os.getenv('PAXXSERV_API')}

        try:
            pdf_url = firebase_storage.upload_file(file, g.uid, 'documents')
        except Exception as e:
            print(f"Error uploading pdf to storage: {e}")
            return jsonify({'message': 'Failed to upload pdf to storage'}), 500
        
        try:
            payload = {'url': pdf_url}
            response = requests.request("POST", f"{firecrawl_url}/scrape", json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            reponse_data = response.json()
            data = reponse_data['data']
            content = g.kb_services.save_embed_pdf(data, kb_id)
            return jsonify({'content': content}), 200
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}") 
            return jsonify({'message': 'Failed to extract text'}), 500
        except ValueError as json_err:
            print(f"JSON decode error: {json_err}, Response: {response.text}")  
            return jsonify({'message': 'Invalid response from server'}), 500
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return jsonify({'message': 'Failed to extract text'}), 500

    if request.method == "GET" and subpath == "documents":
        kb_id = request.headers.get('KB-ID')
        if not kb_id:
            return jsonify({'message': 'KB ID is required'}), 400
        
        documents = g.kb_services.get_docs_by_kbId(kb_id)
        return jsonify({'documents': documents}), 200
    
    if request.method == "POST" and subpath == "extract":
        db_name = request.headers.get('dbName', 'paxxium')
        uid = request.headers.get('uid')
        mongo_client = MongoDbClient(db_name)
        db = mongo_client.connect()
        kb_services = KnowledgeBaseService(db, uid)
        data = request.get_json()
        kb_id = data.get('kbId')
        url = data.get('url')
        normalized_url = kb_services.normalize_url(url)
        endpoint = data.get('endpoint')
        def generate():
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
                    job_id = firecrawl_data['jobId']
                    
                    while True:
                        status_response = requests.get(f"{firecrawl_url}/crawl/status/{job_id}", headers=headers, timeout=10)
                        if not status_response.ok:
                            yield f'{{"status": "error", "message": "Failed to check {job_id} status"}}'
                            return
                        
                        status_data = status_response.json()
                        if status_data['status'] == 'completed':
                            content = status_data['data']
                            break
                        elif status_data['status'] == 'failed':
                            yield f'{{"status": "error", "message": "Crawl job {job_id} failed"}}'
                            return
                        
                        yield f'{{"status": "in_progress", "message": "Crawling in progress..."}}'
                        time.sleep(5)
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
                    # Need to handle when we are crawling a site. I would probably want to add
                    # a new field in the doc to hold the different pages within the site.
                    # Then here I would need to update the doc with each page.
                    new_doc = kb_services.create_kb_doc_in_db(kb_id, markdown, source_url, 'url')
                    url_docs.append(new_doc)
                    yield f'{{"status": "processing", "message": "Processing {source_url}"}}'

                yield f'{{"status": "completed", "content": {json.dumps(url_docs)}}}'

            except Exception as e:
                print(f"Error crawling site: {e}")
                yield f'{{"status": "error", "message": "Failed to crawl site: {str(e)}"}}'

        return Response(stream_with_context(generate()), content_type='text/event-stream')
    
    if request.method == "POST" and subpath == "embed":
        data = request.get_json()
        content = data.get('content')
        highlights = data.get('highlights')
        doc_id = data.get('docId')
        kb_id = data.get('kbId')
        source = data.get('source')

        embedded_chunks = g.kb_services.chunk_and_embed_content(content, source, kb_id, doc_id, highlights)
        return jsonify({'embedded_chunks': embedded_chunks}), 200
    
    if request.method == "DELETE" and subpath == "documents":
        data = request.get_json()
        doc_id = data.get('docId')
        if not doc_id:
            return jsonify({'message': 'Doc ID is required'}), 400

        g.kb_services.delete_doc_by_id(doc_id)
        return jsonify({'message': 'Document deleted'}), 200
    
    if request.method == "POST" and subpath == "save_doc":
        data = request.get_json()
        kb_id = data.get('kbId')
        text = data.get('text')
        highlights = data.get('highlights')
        doc_id = data.get('docId')
        source = data.get('source')

        result = g.kb_services.create_kb_doc_in_db(kb_id, text, source, 'url', highlights, doc_id)
        
        if result == 'not_found':
            return jsonify({'message': 'Document not found'}), 404
        else:
            return jsonify({'message': 'Text doc saved', 'docId': result}), 200
    
    