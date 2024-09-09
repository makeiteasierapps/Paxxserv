import uvicorn
import argparse
from app import create_app

app = create_app()

def main(debug=False):
    if debug:
        uvicorn.run("run:app", host="0.0.0.0", port=3033, reload=True)
    else:
        uvicorn.run("run:app", host="0.0.0.0", port=3033, workers=1, log_level="info")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the application in production or development mode.')
    parser.add_argument('--dev', action='store_true', help='Run in development mode with debugging and hot reloading')
    args = parser.parse_args()

    main(debug=args.dev)
