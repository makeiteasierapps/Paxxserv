import argparse
from gevent import monkey
monkey.patch_all()

from app import create_app, socketio

def main(debug=False):
    app = create_app()
    socketio.run(app, host='0.0.0.0', port=3033, debug=debug, use_reloader=debug)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the application in production or development mode.')
    parser.add_argument('--dev', action='store_true', help='Run in development mode with debugging and hot reloading')
    args = parser.parse_args()

    main(debug=args.dev)