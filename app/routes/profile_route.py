import json
import traceback
from flask import Blueprint, request, jsonify, g, Response, current_app, stream_with_context
from dotenv import load_dotenv
from app.services.ProfileService import ProfileService
from app.services.UserService import UserService
from app.services.MongoDbClient import MongoDbClient
from app.agents.QuestionGenerator import QuestionGenerator
from app.agents.AnalyzeUser import AnalyzeUser

load_dotenv()

profile_bp = Blueprint('profile_bp', __name__)

@profile_bp.before_request
def initialize_services():
    if request.method == "OPTIONS":
        return "", 204
    db_name = request.headers.get('dbName', 'paxxium')
    g.uid = request.headers.get('uid')
    g.mongo_client = MongoDbClient(db_name)
    db = g.mongo_client.connect()
    g.profile_service = ProfileService(db, g.uid)
    g.user_service = UserService(db)
    g.analyze_user = AnalyzeUser(db, g.uid)

@profile_bp.after_request
def close_mongo_connection(response):
    if hasattr(g, 'mongo_client'):
        g.mongo_client.close()
    return response

@profile_bp.route('/profile', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@profile_bp.route('/profile/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def profile(subpath):
    if request.method == 'GET' and subpath == '':
        user_profile = g.profile_service.get_profile(g.uid)
        return jsonify(user_profile), 200

    if subpath == 'generate_questions':
        content = request.get_json()
        db_name = request.headers.get('dbName', 'paxxium')
        uid = request.headers.get('uid')
        mongo_client = MongoDbClient(db_name)
        db = mongo_client.connect()
        db['users'].update_one({'_id': uid}, {'$set': {'userintro': content['userInput']}})
        def generate():
            with current_app.app_context():
                try:
                    mongo_client = MongoDbClient(db_name)
                    db = mongo_client.connect()
                    question_generator = QuestionGenerator(db, uid)
                    for result in question_generator.generate_questions(content['userInput']):
                        yield json.dumps(result) + '\n'
                except Exception as e:
                    error_msg = f"Error in generate_questions: {str(e)}\n{traceback.format_exc()}"
                    current_app.logger.error(error_msg)
                    yield json.dumps({"error": error_msg}) + '\n'
                finally:
                    if 'mongo_client' in locals():
                        mongo_client.close()
                    yield ''  # Ensure the stream is properly closed
        
        return Response(stream_with_context(generate()), content_type='application/json'), 200
    
    if subpath == 'questions':
        if request.method == 'GET':
            questions = g.profile_service.load_questions(g.uid)
            return jsonify(questions), 200
        
    if subpath == 'answers':
        if request.method == 'POST':
            data = request.get_json()
            question_id = data['questionId']
            answer = data['answer']
            g.profile_service.update_profile_answer(question_id, answer)
            return jsonify({'response': 'Profile questions/answers updated successfully'}), 200

    if subpath == 'user':
        data = request.get_json()
        g.profile_service.update_user_profile(g.uid, data)
        return jsonify({'response': 'User profile updated successfully'}), 200
    
    if subpath == 'analyze':
        answered_questions = g.profile_service.load_questions(g.uid, fetch_answered=True)
        response = g.analyze_user.analyze_cateogry(answered_questions)
        # response = g.profile_service.analyze_user_profile(prompt)
        # analysis_obj = json.loads(response)
        # g.profile_service.update_user_profile(g.uid, analysis_obj.copy())
        return jsonify(answered_questions), 200

    if subpath in ('update_avatar', 'profile/update_avatar'):
        file = request.files['avatar']
        avatar_url = g.user_service.update_user_avatar(file, g.uid)
        return jsonify({'avatar_url': avatar_url}), 200

    return 'Not Found', 404

    
    