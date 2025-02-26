from app.socket_handlers.chat_handler import setup_chat_handlers
from app.socket_handlers.document_handler import setup_document_handlers
from app.socket_handlers.file_system_handler import setup_file_system_handlers
from app.socket_handlers.system_agent_handler import setup_system_agent_handlers
from app.socket_handlers.insight_agent_handler import setup_insight_agent_handlers

def setup_socket_handlers(sio, app):
    setup_chat_handlers(sio, app.state.mongo_client)
    setup_document_handlers(sio, app.state.mongo_client)
    setup_file_system_handlers(sio, app.state.system_state_manager)
    setup_system_agent_handlers(sio, app.state.system_state_manager, app.state.mongo_client)
    setup_insight_agent_handlers(sio, app.state.mongo_client)