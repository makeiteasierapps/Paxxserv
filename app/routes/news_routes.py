from fastapi import APIRouter, Header, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Any
import random
from dotenv import load_dotenv
from app.services.NewsService import NewsService
from app.services.UserService import UserService
from fastapi import Request

load_dotenv()

router = APIRouter()

def get_db(request: Request):
    try:
        mongo_client = request.app.state.mongo_client
        db = mongo_client.db
        return db
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

def get_services(db: Any = Depends(get_db), uid: str = Header(...)):
    user_service = UserService(db)
    news_service = NewsService(db, uid)
    return user_service, news_service

@router.get("/news")
async def get_news(services: tuple = Depends(get_services)):
    _, news_service = services
    news_data = await news_service.get_all_news_articles()
    for article in news_data:
        article['_id'] = str(article['_id'])
    return JSONResponse(content=news_data)

@router.post("/news")
async def post_news(request: Request, services: tuple = Depends(get_services)):
    _, news_service = services
    data = await request.json()
    query = data['query']
    urls = news_service.get_article_urls(query)
    news_data = news_service.summarize_articles(urls)
    news_service.upload_news_data(news_data)
    return JSONResponse(content=news_data)

@router.put("/news")
async def update_news(request: Request, services: tuple = Depends(get_services)):
    _, news_service = services
    data = await request.json()
    doc_id = data['articleId']
    is_read = data['isRead']
    news_service.mark_is_read(doc_id, is_read)
    return JSONResponse(content={"message": "Updated successfully"})

@router.delete("/news")
async def delete_news(request: Request, services: tuple = Depends(get_services)):
    _, news_service = services
    data = await request.json()
    doc_id = data['articleId']
    news_service.delete_news_article(doc_id)
    return JSONResponse(content={"message": "Deleted successfully"})

@router.get("/ai-fetch-news")
async def ai_fetch_news(services: tuple = Depends(get_services)):
    _, news_service = services
    topics = news_service.get_user_topics()
    if not topics:
        raise HTTPException(status_code=404, detail="No topics found, please answer some questions in the profile section and analyze")
    
    random_topic = random.choice(topics)
    urls = news_service.get_article_urls(random_topic)
    news_data_list = news_service.summarize_articles(urls)
    news_service.upload_news_data(news_data_list)
    return JSONResponse(content=news_data_list)