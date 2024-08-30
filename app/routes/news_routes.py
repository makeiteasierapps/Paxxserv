import random
from flask import Blueprint, request, g
from dotenv import load_dotenv
from app.services.NewsService import NewsService
from app.services.UserService import UserService
from app.services.MongoDbClient import MongoDbClient

load_dotenv()

news_bp = Blueprint('news_bp', __name__)

@news_bp.before_request
def initialize_services():
    if request.method == "OPTIONS":
        return ("", 204)
    db_name = request.headers.get('dbName', 'paxxium')
    g.uid = request.headers.get('uid')
    g.mongo_client = MongoDbClient(db_name)
    db = g.mongo_client.connect()
    g.user_service = UserService(db)
    g.news_service = NewsService(db, g.uid)

@news_bp.after_request
def close_mongo_connection(response):
    if hasattr(g, 'mongo_client'):
        g.mongo_client.close()
    return response

@news_bp.route('/news', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def news():
    if request.method == 'GET':
        news_data = g.news_service.get_all_news_articles()
        # Convert ObjectId to string
        for article in news_data:
            article['_id'] = str(article['_id'])
        return (news_data, 200)

    if request.method == 'POST':
        data = request.get_json()
        query = data['query']
        urls = g.news_service.get_article_urls(query)
        news_data = g.news_service.summarize_articles(urls)
        g.news_service.upload_news_data(news_data)
        return (news_data, 200)
    
    if request.method == 'PUT':
        data = request.get_json()
        doc_id = data['articleId']
        is_read = data['isRead']
        g.news_service.mark_is_read(doc_id, is_read)
        return ({"message": "Updated successfully"}, 200)

    if request.method == 'DELETE':
        data = request.get_json()
        doc_id = data['articleId']
        g.news_service.delete_news_article(doc_id)
        return ({"message": "Deleted successfully"}, 200)

@news_bp.route('/ai-fetch-news', methods=['GET', 'OPTIONS'])
def ai_fetch_news():
    if request.method == 'GET':
        topics = g.news_service.get_user_topics()
        if not topics:
            return ({"message": "No topics found, please answer some questions in the profile section and analyze"}, 404)

        random_topic = random.choice(topics)
        urls = g.news_service.get_article_urls(random_topic)
        news_data_list = g.news_service.summarize_articles(urls)
        g.news_service.upload_news_data(news_data_list)
        return (news_data_list, 200)
    
    