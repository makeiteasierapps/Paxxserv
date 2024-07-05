import os
from pymongo import MongoClient
from flask import Blueprint, g
import certifi
from dotenv import load_dotenv
from flask import jsonify, request
from firebase_admin import credentials, initialize_app
from app.services.FirebaseService import FirebaseService
from app.services.ProjectService import ProjectService

load_dotenv()

projects_bp = Blueprint('projects_bp', __name__)

cred = credentials.Certificate(os.getenv('FIREBASE_ADMIN_SDK'))

try:
    initialize_app(cred, {
        'projectId': 'paxxiumv1',
        'storageBucket': 'paxxiumv1.appspot.com'
    })
except ValueError:
    pass

mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri, tlsCAFile=certifi.where())

db = client['paxxium']
firebase_service = FirebaseService()
project_services = ProjectService(db)

def verify_request_token():
    id_token = request.headers.get('Authorization')
    if not id_token:
        return None  # Token missing
    
    decoded_token = firebase_service.verify_id_token(id_token)
    if not decoded_token:
        return None  # Token invalid
    
    return decoded_token['uid']  # Return UID if successful

def generate_token_error_response():
    message = 'Missing token' if 'Authorization' not in request.headers else 'Invalid token'
    return jsonify({'message': message}), 403

@projects_bp.before_request
def before_request():
    g.uid = verify_request_token()

@projects_bp.route('/projects', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@projects_bp.route('/projects/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def projects(subpath):

    if request.method == "OPTIONS":
        return ("", 204)
    
    if g.uid is None:
        return generate_token_error_response()
    
    if request.method == "GET" and subpath == '':
        project_list = project_services.get_projects(g.uid)
        return jsonify({'projects': project_list}), 200
    
    if request.method == "POST" and subpath == '':
        data = request.get_json()
        name = data.get('name')
        objective = data.get('objective')
        
        new_project_details, new_chat_details = project_services.create_new_project(g.uid, name, objective)
        return jsonify({'new_project': new_project_details, 'new_chat': new_chat_details}), 200
    
    if request.method == "DELETE" and subpath == '':
        data = request.get_json()
        project_id = data.get('projectId')
        if not project_id:
            return jsonify({'message': 'Project ID is required'}), 400
        project_services.delete_project_by_id(project_id)
        return jsonify({'message': 'Project deleted'}), 200
    
    if subpath == "scrape":
        data = request.get_json()
        crawl_entire_site = data.get('crawlEntireSite')
    
        if crawl_entire_site:
            urls = data.get('urls')
            project_id = data.get('projectId')
            name = data.get('projectName')
            if not urls:
                return jsonify({'message': 'URL is required'}), 400
            new_docs = project_services.crawl_site(urls[0], project_id)
            return jsonify({'docs': new_docs}), 200
    
        urls = data.get('urls')
        project_id = data.get('projectId')
        name = data.get('projectName')
    
        if not urls or not isinstance(urls, list) or not all(urls):
            return jsonify({'message': 'URLs are required and must be a non-empty list'}), 400

        docs = []
        for url in urls:
            new_doc = project_services.scrape_url(url, project_id)
            docs.append(new_doc)

        return jsonify({'docs': docs}), 200,

    if subpath == "extract":
        file = request.files.get('file')
    
        if not file:
            return jsonify({'message': 'No file part'}), 400

        project_name = request.form.get('projectName')
        project_id = request.form.get('projectId')

        if not project_name:
            return jsonify({'message': 'Project name is required'}), 400

        # Check if the file is a PDF
        if not file.filename.endswith('.pdf'):
            return jsonify({'message': 'File is not a PDF'}), 400
        
        try:
            text = project_services.extract_pdf(file, project_id)
            
            return jsonify({'message': 'Extracted', 'text': text}), 200
        
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return jsonify({'message': 'Failed to extract text'}), 500
    
    if request.method == "GET" and subpath == "documents":
        project_id = request.headers.get('Project-ID')
        if not project_id:
            return jsonify({'message': 'Project ID is required'}), 400
        
        documents = project_services.get_docs_by_projectId(project_id)
        return jsonify({'documents': documents}), 200
    
    if request.method == "DELETE" and subpath == "documents":
        data = request.get_json()
        doc_id = data.get('docId')
        if not doc_id:
            return jsonify({'message': 'Doc ID is required'}), 400

        project_services.delete_doc_by_id(doc_id)
        return jsonify({'message': 'Document deleted'}), 200
    
    if request.method == "POST" and subpath == "save_text_doc":
        data = request.get_json()
        project_id = data.get('projectId')
        text = data.get('text')
        category = data.get('category')
        category = category.lower() if category else None
        highlights = data.get('highlights')
        doc_id = data.get('docId')

        result = project_services.save_text_doc(project_id, text, highlights, doc_id, category)
        
        if result == 'not_found':
            return jsonify({'message': 'Document not found'}), 404
        else:
            return jsonify({'message': 'Text doc saved', 'docId': result}), 200
    
    if request.method == "GET" and subpath == "text_doc":
        project_id = request.args.get('projectId')
        doc_list = project_services.get_text_docs(project_id)
        return doc_list, 200
    
    if request.method == "POST" and subpath == "embed":
        data = request.get_json()
        doc = data.get('doc')
        category = data.get('category').lower()
        highlights = data.get('highlights')
        doc_id = data.get('docId')
        project_id = data.get('projectId')

        embedded_chunks = project_services.embed_text_doc(doc_id, project_id, doc, highlights, category)
        return jsonify({'embedded_chunks': embedded_chunks}), 200