import argparse
from gevent import monkey
monkey.patch_all()

from app import create_app, socketio

app = create_app()

def main(debug=False):

    if debug:
        socketio.run(app, host='0.0.0.0', port=3033, debug=True, use_reloader=True)
    else:
        pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the application in production or development mode.')
    parser.add_argument('--dev', action='store_true', help='Run in development mode with debugging and hot reloading')
    args = parser.parse_args()

    main(debug=args.dev)
