import random
from flask import Blueprint, request, g
from dotenv import load_dotenv
from app.services.NewsService import NewsService
from app.services.UserService import UserService
from app.agents.BossAgent import BossAgent
from app.services.MongoDbClient import MongoDbClient

load_dotenv()

news_bp = Blueprint('news_bp', __name__)

@news_bp.before_request
def initialize_services():
    if request.method == "OPTIONS":
        return ("", 204)
    db_name = request.headers.get('dbName', 'paxxium')
    g.uid = request.headers.get('uid')
    
    with MongoDbClient(db_name) as db:
        g.user_service = UserService(db)
        openai_key = g.user_service.get_keys(g.uid)
        g.openai_client = BossAgent.get_openai_client(api_key=openai_key)
        g.news_service = NewsService(db, g.uid, g.openai_client)

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
        g.news_service.mark_is_read(doc_id)
        return ({"message": "Updated successfully"}, 200) 
    
    if request.method == 'DELETE':
        data = request.get_json()
        doc_id = data['articleId']
        g.news_service.delete_news_article(doc_id)
        return ({"message": "Deleted successfully"}, 200)
    
@news_bp.route('/ai-fetch-news', methods=['GET', 'OPTIONS'])
def ai_fetch_news():
    if request.method == 'GET':
        news_topics = g.news_service.get_user_news_topics()
        if not news_topics:
            return ({"message": "No news topics found, please answer some questions in the profile section and analyze"}, 404)
        
        random_topic = random.choice(news_topics)
        urls = g.news_service.get_article_urls(random_topic)
        
        news_data = g.news_service.summarize_articles(urls)
        g.news_service.upload_news_data(news_data)
        return (news_data, 200)
    
    