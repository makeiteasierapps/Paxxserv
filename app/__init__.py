from dotenv import load_dotenv
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import credentials, initialize_app
import logging
import socketio

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase
cred = credentials.Certificate(os.getenv('FIREBASE_ADMIN_SDK'))
try:
    initialize_app(cred, {
        'projectId': 'paxxiumv1',
        'storageBucket': 'paxxiumv1.appspot.com'
    })
    logger.info("Firebase initialized successfully")
except ValueError as e:
    logger.error(f"Firebase initialization failed: {e}")

def create_app():
    app = FastAPI()
    sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
    socket_app = socketio.ASGIApp(sio, app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://paxxiumv1.web.app", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE", "PATCH"],
        allow_headers=["Content-Type", "Accept", "dbName", "uid"],
    )

    # Import and include routers
    from .routes import (
        chat_route, sam_route, moments_route, auth_check_route, 
        images_route, news_routes, signup_route, profile_route, kb_route, socket_handler
    )
    
    routers = [
        chat_route.router,
        sam_route.router,
        moments_route.router,
        auth_check_route.router,
        images_route.router,
        profile_route.router,
        news_routes.router,
        signup_route.router,
        kb_route.router,
    ]
    
    for router in routers:
        app.include_router(router)

    # Setup Socket.IO event handlers
    socket_handler.setup_socketio_events(sio)

    return socket_app
