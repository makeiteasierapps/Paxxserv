from app import create_app
from config import config

import os

config_name = os.getenv('FLASK_CONFIG', 'development')
app = create_app(config[config_name])

if __name__ == '__main__':
    app.run(host='0.0.0.0')