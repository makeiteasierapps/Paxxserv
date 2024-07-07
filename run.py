import argparse
from app import create_app
from hypercorn.config import Config
from hypercorn.asyncio import serve
import asyncio

app = create_app()

def main():
    parser = argparse.ArgumentParser(description="Run the server.")
    parser.add_argument('--mode', choices=['dev', 'prod'], default='prod', help='Run mode: dev or prod')
    args = parser.parse_args()

    config = Config()
    config.bind = ["0.0.0.0:3033"]

    if args.mode == 'dev':
        config.use_reloader = True
    else:
        config.use_reloader = False

    asyncio.run(serve(app, config))

if __name__ == '__main__':
    main()