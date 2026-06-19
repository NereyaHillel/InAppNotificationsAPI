from flask import Flask, request
from flasgger import Swagger
from routes import initialize_routes
import os

import routes

app = Flask(__name__, template_folder='templates')
swagger = Swagger(app)

routes.initialize_routes(app)

if __name__ == '__main__':
    port=int(os.getenv('PORT', 5000))
    app.run(debug=True, port=port)