from controllers.in_app_notifications import in_app_notifications_bp
def initialize_routes(app):
    app.register_blueprint(in_app_notifications_bp)