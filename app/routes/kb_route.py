from flask import Blueprint, Response, stream_with_context
from dotenv import load_dotenv
from flask import jsonify, request, g
from app.services.KnowledgeBaseService import KnowledgeBaseService
from app.services.MongoDbClient import MongoDbClient
from app.services.ExtractionService import ExtractionService

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
        extraction_service = ExtractionService(db, uid)
        
        if 'file' in request.files:
            file = request.files['file']
            kb_id = request.form.get('kbId')
            if file and file.filename.endswith('.pdf'):
                return extraction_service.extract_from_pdf(file, kb_id, uid, kb_services)
            else:
                return jsonify({'message': 'Invalid file type. Only PDF files are allowed.'}), 400
        elif request.is_json:
            data = request.get_json()
            kb_id = data.get('kbId')
            url = data.get('url')
            normalized_url = kb_services.normalize_url(url)
            endpoint = data.get('endpoint', 'scrape')
            
            def generate():
                yield from extraction_service.extract_from_url(normalized_url, kb_id, endpoint, kb_services)

            return Response(stream_with_context(generate()), content_type='text/event-stream')
        else:
            return jsonify({'message': 'No file or URL provided'}), 400
    
    if request.method == "POST" and subpath == "embed":
        data = request.get_json()
        content = data.get('content')
        highlights = data.get('highlights')
        doc_id = data.get('id')
        kb_id = data.get('kbId')
        source = data.get('source')

        kb_doc = g.kb_services.chunk_and_embed_content(content, source, kb_id, doc_id, highlights)
        
        return jsonify({'kb_doc': kb_doc}), 200
    
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
        content = data.get('content')
        highlights = data.get('highlights')
        doc_id = data.get('id')
        source = data.get('source')

        result = g.kb_services.create_kb_doc_in_db(kb_id, content, source, 'url', highlights, doc_id)
        
        if result == 'not_found':
            return jsonify({'message': 'Document not found'}), 404
        else:
            return jsonify({'message': 'Text doc saved', 'kb_doc': result}), 200
    
    