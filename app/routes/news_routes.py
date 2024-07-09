import random
from flask import Blueprint, request, g
from dotenv import load_dotenv
from app.services.NewsService import NewsService

load_dotenv()

news_bp = Blueprint('news_bp', __name__)

@news_bp.before_request
def initialize_services():
    db_name = request.headers.get('dbName', 'paxxium')
    g.news_service = NewsService(db_name=db_name)
    g.uid = request.headers.get('uid')

@news_bp.route('/news', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def news():
    if request.method == "OPTIONS":
        return ("", 204)
    
    if request.method == 'GET':
        news_data = g.news_service.get_all_news_articles(g.uid)
        # Convert ObjectId to string
        for article in news_data:
            article['_id'] = str(article['_id'])
        return (news_data, 200)

    if request.method == 'POST':
        data = request.get_json()
        query = data['query']
        urls = g.news_service.get_article_urls(query)
        news_data = g.news_service.summarize_articles(urls)
        g.news_service.upload_news_data(g.uid, news_data)
        return (news_data, 200)
    
    if request.method == 'PUT':
        data = request.get_json()
        doc_id = data['articleId']
        g.news_service.mark_is_read(g.uid, doc_id)
        return ({"message": "Updated successfully"}, 200) 
    
    if request.method == 'DELETE':
        data = request.get_json()
        doc_id = data['articleId']
        g.news_service.delete_news_article(g.uid, doc_id)
        return ({"message": "Deleted successfully"}, 200)
    
@news_bp.route('/ai-fetch-news', methods=['GET', 'OPTIONS'])
def ai_fetch_news():
    if request.method == "OPTIONS":
        return ("", 204)
    
    if request.method == 'GET':
        news_topics = g.news_service.get_user_news_topics(g.uid)
        if not news_topics:
            return ({"message": "No news topics found, please answer some questions in the profile section and analyze"}, 404)
        
        random_topic = random.choice(news_topics)
        urls = g.news_service.get_article_urls(random_topic)
        
        news_data = g.news_service.summarize_articles(urls)
        g.news_service.upload_news_data(g.uid, news_data)
        return (news_data, 200)
    
    