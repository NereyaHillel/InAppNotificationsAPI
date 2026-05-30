from flask import Blueprint, request, jsonify


in_app_notifications_bp = Blueprint('in_app_notifications_bp', __name__)

@in_app_notifications_bp.route('/in-app-notifications', methods=['POST'])
def create_notification():
    """Create a new in-app notification
    ---    
    tags:
      - In-App Notifications
    parameters:
      - name: in_app_notification
        in: body
        required: true
        description: Notification details to be created
        schema:
          type: object
          id: InAppNotification
          required:
            - user_id
            - message
          properties:
            user_id:
              type: string
              description: ID of the user to receive the notification
            message:
              type: string
              description: Notification message content
    responses:
        201:
            description: Notification created successfully
        400:
            description: Invalid input
        500:
            description: Internal server error
        """
    # Logic to create a new in-app notification
    data = request.get_json()
    user_id = data.get('user_id')
    message = data.get('message')
    
    # Logic to create a new in-app notification
    return jsonify({"user_id": user_id, "message": message}), 201
