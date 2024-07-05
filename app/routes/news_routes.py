import os
import random
import certifi
from flask import Blueprint, request
from pymongo import MongoClient
from dotenv import load_dotenv
from firebase_admin import credentials, initialize_app

from app.services.FirebaseService import FirebaseService
from app.services.NewsService import NewsService
load_dotenv()

news_bp = Blueprint('news_bp', __name__)
cred = credentials.Certificate(os.getenv('FIREBASE_ADMIN_SDK'))

try:
    initialize_app(cred, {
        'projectId': 'paxxiumv1',
        'storageBucket': 'paxxiumv1.appspot.com'
    })
except ValueError:
    pass

# MongoDB URI
mongo_uri = os.getenv('MONGO_URI')
# Create a new MongoClient and connect to the server
client = MongoClient(mongo_uri, tlsCAFile=certifi.where())

db = client['paxxium']
firebase_service = FirebaseService()
news_service = NewsService(db)

@news_bp.route('/news', methods=['GET', 'POST', 'PUT', 'DELETE'])
def news():
    if request.method == "OPTIONS":
        return ("", 204)
    id_token = request.headers.get('Authorization')
    if not id_token:
        return ('Missing token', 403)

    decoded_token = firebase_service.verify_id_token(id_token)
    if not decoded_token:
        return ('Invalid token', 403)

    uid = decoded_token['uid']
    
    if request.method == 'GET':
        news_data = news_service.get_all_news_articles(uid)
        # Convert ObjectId to string
        for article in news_data:
            article['_id'] = str(article['_id'])
        return (news_data, 200)

    if request.method == 'POST':
        data = request.get_json()
        query = data['query']
        urls = news_service.get_article_urls(query)
        news_data = news_service.summarize_articles(urls)
        news_service.upload_news_data(uid, news_data)

        return (news_data, 200)
    
    if request.method == 'PUT':
        data = request.get_json()
        doc_id = data['articleId']
        news_service.mark_is_read(uid, doc_id)
        return ({"message": "Updated successfully"}, 200) 
    
    if request.method == 'DELETE':
        data = request.get_json()
        doc_id = data['articleId']
        news_service.delete_news_article(uid, doc_id)
        return ({"message": "Deleted successfully"}, 200)
    
@news_bp.route('/ai-fetch-news', methods=['GET'])
def ai_fetch_news():
    if request.method == "OPTIONS":
        return ("", 204)
    id_token = request.headers.get('Authorization')

    if not id_token:
        return ('Missing token', 403)

    decoded_token = firebase_service.verify_id_token(id_token)
    if not decoded_token:
        return ('Invalid token', 403)

    uid = decoded_token['uid']
    if request.method == 'GET':
        news_topics = news_service.get_user_news_topics(uid)
        if not news_topics:
            return ({"message": "No news topics found, please answer some questions in the profile section and analyze"}, 404, headers)
        
        random_topic = random.choice(news_topics)
        urls = news_service.get_article_urls(random_topic)
        
        news_data = news_service.summarize_articles(urls)
        news_service.upload_news_data(uid, news_data)
        return (news_data, 200)
    
    