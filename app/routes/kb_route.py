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
def extract_from_pdf(file, kb_id, uid, db, kb_services):
    firecrawl_url = os.getenv('FIRECRAWL_URL')
    headers = {'api': os.getenv('PAXXSERV_API')}

    try:
        pdf_url = firebase_storage.upload_file(file, uid, 'documents')
        payload = {'url': pdf_url}
        response = requests.post(f"{firecrawl_url}/scrape", json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        response_data = response.json()
        data = response_data['data']
        content = kb_services.save_embed_pdf(data, kb_id)
        return jsonify({'content': content}), 200
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return jsonify({'message': 'Failed to extract text from PDF'}), 500

def extract_from_url(normalized_url, kb_id, endpoint, kb_services):
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
            content = poll_job_status(firecrawl_url, firecrawl_data['jobId'], headers)
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
            new_doc = kb_services.create_kb_doc_in_db(kb_id, markdown, source_url, 'url')
            url_docs.append(new_doc)
            yield f'{{"status": "processing", "message": "Processing {source_url}"}}'

        yield f'{{"status": "completed", "content": {json.dumps(url_docs)}}}'

    except Exception as e:
        print(f"Error crawling site: {e}")
        yield f'{{"status": "error", "message": "Failed to crawl site: {str(e)}"}}'

def poll_job_status(firecrawl_url, job_id, headers):
    while True:
        status_response = requests.get(f"{firecrawl_url}/crawl/status/{job_id}", headers=headers, timeout=10)
        status_response.raise_for_status()
        status_data = status_response.json()
        
        if status_data['status'] == 'completed':
            return status_data['data']
        elif status_data['status'] == 'failed':
            raise Exception(f"Crawl job {job_id} failed")
        
        time.sleep(5)

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
        
        if 'file' in request.files:
            file = request.files['file']
            kb_id = request.form.get('kbId')
            if file and file.filename.endswith('.pdf'):
                return extract_from_pdf(file, kb_id, uid, db, kb_services)
            else:
                return jsonify({'message': 'Invalid file type. Only PDF files are allowed.'}), 400
        elif request.is_json:
            data = request.get_json()
            kb_id = data.get('kbId')
            url = data.get('url')
            normalized_url = kb_services.normalize_url(url)
            endpoint = data.get('endpoint', 'scrape')
            
            def generate():
                yield from extract_from_url(normalized_url, kb_id, endpoint, kb_services)

            return Response(stream_with_context(generate()), content_type='text/event-stream')
        else:
            return jsonify({'message': 'No file or URL provided'}), 400
    
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
    
    