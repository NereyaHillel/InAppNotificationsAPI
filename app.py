from flask import Flask, request
from flasgger import Swagger
from routes import initialize_routes
from DB_Connector import DBConnector
import os
import logging

import routes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')
swagger = Swagger(app)

# Initialize database on app startup
with app.app_context():
    DBConnector.initialize_db()

routes.initialize_routes(app)

if __name__ == '__main__':
    port=int(os.getenv('PORT', 5000))
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, port=port)