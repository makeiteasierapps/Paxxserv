import sys
import traceback
import json
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    mongo_client = MongoDbClient('paxxium')
    app.state.mongo_client = mongo_client
    app.state.system_state_manager = await SystemStateManager.get_instance(mongo_client)
    
    # Setup Socket.IO event handlers after system_state_manager is initialized
    from app.socket_handlers.setup_socket_handlers import setup_socket_handlers
    setup_socket_handlers(socket_client, app)
    
    yield

async def error_handling_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        stack_trace = traceback.format_exception(exc_type, exc_value, exc_traceback)
        
        logger.error(f"Unhandled error: {str(e)}")
        logger.error(f"Stack trace: {''.join(stack_trace)}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "type": exc_type.__name__,
                "stack_trace": stack_trace
            }
        )

def create_app():
    app = FastAPI(lifespan=lifespan)
    socket_app = socketio.ASGIApp(socket_client, app)

    app.middleware("http")(error_handling_middleware)

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
        news_routes, signup_route, insight_route, kb_route, systems_route, profile_route
    )
    
    # Create chat routers
    default_chat_router = chat_route.create_chat_router()
    system_chat_router = chat_route.create_chat_router(prefix="/system", chat_type="system")
    
    routers = [
        default_chat_router,
        system_chat_router,
        systems_route.router,
        sam_route.router,
        moments_route.router,
        auth_route.router,
        images_route.router,
        insight_route.router,
        profile_route.router,
        news_routes.router,
        signup_route.router,
        kb_route.router,
    ]
    
    for router in routers:
        app.include_router(router)

    return socket_app