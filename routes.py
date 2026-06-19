from controllers.in_app_notifications import in_app_notifications_bp
from controllers.dashboard import dashboard_bp

def initialize_routes(app):
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(in_app_notifications_bp)