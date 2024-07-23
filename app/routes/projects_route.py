from flask import Blueprint, Response, stream_with_context
import requests
import os
import time
from dotenv import load_dotenv
from flask import jsonify, request, g
from app.services.ProjectService import ProjectService
from app.services.MongoDbClient import MongoDbClient
from app.services.FirebaseStoreageService import FirebaseStorageService as firebase_storage

load_dotenv()

projects_bp = Blueprint('projects_bp', __name__)

@projects_bp.before_request
def initialize_services():
    if request.method == "OPTIONS":
        return ("", 204)
    db_name = request.headers.get('dbName')
    g.uid = request.headers.get('uid')
    g.mongo_client = MongoDbClient(db_name)
    db = g.mongo_client.connect()
    g.project_services = ProjectService(db, g.uid)

@projects_bp.after_request
def close_mongo_connection(response):
    if hasattr(g, 'mongo_client'):
        g.mongo_client.close()
    return response

@projects_bp.route('/projects', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@projects_bp.route('/projects/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def projects(subpath):
    if request.method == "GET" and subpath == '':
        project_list = g.project_services.get_projects(g.uid)
        return jsonify({'projects': project_list}), 200
    
    if request.method == "POST" and subpath == '':
        data = request.get_json()
        name = data.get('name')
        objective = data.get('objective')
        
        new_project_details, new_chat_details = g.project_services.create_new_project(g.uid, name, objective)
        return jsonify({'new_project': new_project_details, 'new_chat': new_chat_details}), 200
    
    if request.method == "DELETE" and subpath == '':
        data = request.get_json()
        project_id = data.get('projectId')
        if not project_id:
            return jsonify({'message': 'Project ID is required'}), 400
        g.project_services.delete_project_by_id(project_id)
        return jsonify({'message': 'Project deleted'}), 200
    

    if subpath == "extract":
        firecrawl_url = os.getenv('FIRECRAWL_URL')
        file = request.files.get('file')
    
        if not file:
            return jsonify({'message': 'No file part'}), 400

        # Check if the file is a PDF
        if not file.filename.endswith('.pdf'):
            return jsonify({'message': 'File is not a PDF'}), 400
        
        project_id = request.form.get('projectId')
        headers = {'api': 'truetoself'}

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
            content = g.project_services.save_embed_pdf(data, project_id)
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
        project_id = request.headers.get('Project-ID')
        if not project_id:
            return jsonify({'message': 'Project ID is required'}), 400
        
        documents = g.project_services.get_docs_by_projectId(project_id)
        return jsonify({'documents': documents}), 200
    
    if request.method == "POST" and subpath == "documents":
        db_name = request.headers.get('dbName', 'paxxium')
        uid = request.headers.get('uid')
        mongo_client = MongoDbClient(db_name)
        db = mongo_client.connect()
        project_services = ProjectService(db, uid)
        data = request.get_json()
        project_id = data.get('projectId')
        url = data.get('url')
        endpoint = data.get('endpoint')
        
        def generate():
            firecrawl_url = os.getenv('FIRECRAWL_URL')
            params = {
                'url': url,
                'pageOptions': {
                    'onlyMainContent': True,
                },
            }

            headers = {'api': 'truetoself'}
            try:
                firecrawl_response = requests.post(f"{firecrawl_url}/{endpoint}", json=params, headers=headers, timeout=10)
                if not firecrawl_response.ok:
                    yield f"data: {{'status': 'error', 'message': 'Failed to scrape url'}}\n\n"
                    return

                firecrawl_data = firecrawl_response.json()
                yield f"data: {{'status': 'started', 'message': 'Crawl job started'}}\n\n"

                if 'jobId' in firecrawl_data:
                    job_id = firecrawl_data['jobId']
                    
                    while True:
                        status_response = requests.get(f"{firecrawl_url}/crawl/status/{job_id}", headers=headers, timeout=10)
                        if not status_response.ok:
                            yield f"data: {{'status': 'error', 'message': 'Failed to check {job_id} status'}}\n\n"
                            return
                        
                        status_data = status_response.json()
                        if status_data['status'] == 'completed':
                            content = status_data['data']
                            break
                        elif status_data['status'] == 'failed':
                            yield f"data: {{'status': 'error', 'message': 'Crawl job {job_id} failed'}}\n\n"
                            return
                        
                        yield f"data: {{'status': 'in_progress', 'message': 'Crawling in progress...'}}\n\n"
                        time.sleep(5)
                else:
                    content = [{
                        'markdown': firecrawl_data['data']['markdown'],
                        'metadata': firecrawl_data['data']['metadata'],
                    }]

                for url_content in content:
                    metadata = url_content.get('metadata')
                    markdown = url_content.get('markdown')
                    source_url = metadata.get('sourceURL')
                    project_services.chunk_embed_url(markdown, source_url, project_id)
                    yield f"data: {{'status': 'processing', 'message': 'Processing {source_url}'}}\n\n"

                yield f"data: {{'status': 'completed', 'message': 'URL scraped and embedded', 'content': {content}}}\n\n"

            except Exception as e:
                print(f"Error crawling site: {e}")
                yield f"data: {{'status': 'error', 'message': 'Failed to crawl site: {str(e)}'}}\n\n"

        return Response(stream_with_context(generate()), content_type='text/event-stream')
    
    if request.method == "DELETE" and subpath == "documents":
        data = request.get_json()
        doc_id = data.get('docId')
        if not doc_id:
            return jsonify({'message': 'Doc ID is required'}), 400

        g.project_services.delete_doc_by_id(doc_id)
        return jsonify({'message': 'Document deleted'}), 200
    
    if request.method == "POST" and subpath == "save_text_doc":
        data = request.get_json()
        project_id = data.get('projectId')
        text = data.get('text')
        category = data.get('category')
        category = category.lower() if category else None
        highlights = data.get('highlights')
        doc_id = data.get('docId')

        result = g.project_services.save_text_doc(project_id, text, highlights, doc_id, category)
        
        if result == 'not_found':
            return jsonify({'message': 'Document not found'}), 404
        else:
            return jsonify({'message': 'Text doc saved', 'docId': result}), 200
    
    if request.method == "GET" and subpath == "text_doc":
        project_id = request.args.get('projectId')
        doc_list = g.project_services.get_text_docs(project_id)
        return doc_list, 200
    
    if request.method == "POST" and subpath == "embed":
        data = request.get_json()
        doc = data.get('doc')
        category = data.get('category').lower()
        highlights = data.get('highlights')
        doc_id = data.get('docId')
        project_id = data.get('projectId')

        embedded_chunks = g.project_services.embed_text_doc(doc_id, project_id, doc, highlights, category)
        return jsonify({'embedded_chunks': embedded_chunks}), 200