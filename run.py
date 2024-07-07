from app import create_app
from hypercorn.config import Config
from hypercorn.asyncio import serve
import asyncio

app = create_app()

if __name__ == '__main__':
    config = Config()
    config.bind = ["0.0.0.0:3033"]
    config.use_reloader = True
    asyncio.run(serve(app, config))