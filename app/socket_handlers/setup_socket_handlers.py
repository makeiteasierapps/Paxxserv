from app.socket_handlers.chat_handler import setup_chat_handlers
from app.socket_handlers.document_handler import setup_document_handlers
def setup_socket_handlers(sio):
    setup_chat_handlers(sio)
    setup_document_handlers(sio)
