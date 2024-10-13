import socketio

class SocketClient:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*', max_http_buffer_size=1e8)
        return cls._instance

socket_client = SocketClient.get_instance()