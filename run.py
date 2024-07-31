import argparse
from app import create_app, socketio

app = create_app()

def main():
    parser = argparse.ArgumentParser(description="Run the server.")
    parser.add_argument('--mode', choices=['dev', 'prod'], default='prod', help='Run mode: dev or prod')
    args = parser.parse_args()

    debug = args.mode == 'dev'
    socketio.run(app, host='0.0.0.0', port=3033, debug=debug)

if __name__ == '__main__':
    main()