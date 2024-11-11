from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import credentials, initialize_app
import logging
import socketio
from app.services.SocketClient import socket_client
from app.services.MongoDbClient import MongoDbClient
from app.services.System.SystemStateManager import SystemStateManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase
load_dotenv()
cred = credentials.Certificate(os.getenv('FIREBASE_ADMIN_SDK'))
try:
    initialize_app(cred, {
        'projectId': 'paxxiumv1',
        'storageBucket': 'paxxiumv1.appspot.com'
    })
    logger.info("Firebase initialized successfully")
except ValueError as e:
    logger.error(f"Firebase initialization failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    mongo_client = MongoDbClient.get_instance('paxxium')
    app.state.mongo_client = mongo_client
    app.state.system_state_manager = await SystemStateManager.get_instance(mongo_client)
    
    # Setup Socket.IO event handlers after system_state_manager is initialized
    from app.socket_handlers.setup_socket_handlers import setup_socket_handlers
    setup_socket_handlers(socket_client, app)
    
    yield
    
def create_app():
    app = FastAPI(lifespan=lifespan)
    socket_app = socketio.ASGIApp(socket_client, app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://paxxium.com", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE", "PATCH"],
        allow_headers=["Content-Type", "Accept", "dbName", "uid", 'Kb-ID'],
    )

    # Import and include routers
    from .routes import (
        chat_route, sam_route, moments_route, auth_route, images_route, 
        news_routes, signup_route, profile_route, kb_route, systems_route
    )
    
    routers = [
        chat_route.router,
        sam_route.router,
        moments_route.router,
        auth_route.router,
        images_route.router,
        profile_route.router,
        news_routes.router,
        signup_route.router,
        kb_route.router,
        systems_route.router,
    ]
    
    for router in routers:
        app.include_router(router)

    return socket_app