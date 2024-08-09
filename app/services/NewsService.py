import os
from dotenv import load_dotenv
import requests
from newspaper import Article
import http.client
import json
from bson.objectid import ObjectId
from ..agents.OpenAiClient import OpenAiClient

load_dotenv()

class NewsService(OpenAiClient):
    def __init__(self, db, uid):
        super().__init__(db, uid)
        self.apikey = os.getenv('GNEWS_API_KEY')

    def pass_to_news_agent(self, article_to_summarize, model='gpt-4o-mini'):
        response = self.openai_client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": article_to_summarize,
                }
            ],
        )
        return response.choices[0].message.content
    
    def get_article_urls(self, query):
        conn = http.client.HTTPSConnection("google.serper.dev")
        payload = json.dumps({"q": query, "num": 3})
        headers = {
            'X-API-KEY': os.getenv('SERPER_API_KEY'),
            'Content-Type': 'application/json'
        }
        conn.request("POST", "/search", payload, headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode('utf-8'))
        
        urls = [item['link'] for item in data.get('organic', [])]
        return urls

    def summarize_articles(self, article_urls):
        summarized_articles = []

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'
        }

        session = requests.Session()

        for article_url in article_urls:
            try:
                response = session.get(article_url, headers=headers, timeout=10)
                article = Article(article_url)
                article.download()
                article.parse()
            except Exception as exception:
                print(f"Error occurred while fetching article at {article_url}: {exception}")
                continue

            if response.status_code != 200:
                print(f"Failed to fetch article at {article_url}")
                continue

            # Extract article data
            article_title = article.title
            article_text = article.text

            # Prepare prompt template
            template = f"""You are a very good assistant that summarizes online articles.

            Here's the article you want to summarize.

            ==================
            Title: {article_title}

            {article_text}
            ==================

            Write a summary of the previous article.
            """
            
            summary = self.pass_to_news_agent(template)

            # Create article dictionary
            article_dict = {
                'title': article_title,
                'summary': summary,
                'image': article.top_image,
                'url': article_url,
                'is_read': False,
                'uid': self.uid
            }

            summarized_articles.append(article_dict)

        return summarized_articles

    def upload_news_data(self, news_data_list):
        for news_data in news_data_list:
            url = news_data['url']
            existing_article = self.db['newsArticles'].find_one({'url': url, 'uid': self.uid})

            if existing_article is None:
                self.db['newsArticles'].insert_one(news_data)
                news_data['_id'] = str(news_data['_id'])
                print(f"Added URL '{url}'.")
            else:
                print(f"URL '{url}' already exists, skipping...")

    def get_all_news_articles(self):
        articles_cursor = self.db['newsArticles'].find({'uid': self.uid})
        all_news = list(articles_cursor)

        return all_news

    def get_user_topics(self):
        user_document = self.db['users'].find_one({'_id': self.uid})
        if user_document:
            return user_document.get('topics', [])
        return []

    def mark_is_read(self, doc_id, is_read):
        try:
            result = self.db['newsArticles'].update_one(
                {'_id': ObjectId(doc_id)},  
                {'$set': {'is_read': is_read}}  
            )

            if result.matched_count == 0:
                return "No matching document found"
            
            return "Update successful"
        except Exception as e:
            return f"Update failed: {str(e)}"

    def delete_news_article(self, doc_id):
        try:
            result = self.db['newsArticles'].delete_one({'_id': ObjectId(doc_id)})

            if result.deleted_count == 0:
                return "No matching document found"
            return "Deletion successful"
        except Exception as e:
            return f"Deletion failed: {str(e)}"
