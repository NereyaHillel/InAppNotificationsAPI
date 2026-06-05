from flask import Blueprint, request, jsonify
from DB_Connector import DBConnector
from bson.objectid import ObjectId
from bson.errors import InvalidId

in_app_notifications_bp = Blueprint('in_app_notifications_bp', __name__)

@in_app_notifications_bp.route('/api/v1/sdk/device/register', methods=['POST'])
def register_device():
    """Register a device for in-app notifications
    ---
    tags:
      - In-App Notifications - SDK 
    parameters:
      - name: device_info
        in: body
        required: true
        description: Device information for registration
        schema:
          type: object
          required:
            - device_id
            - user_id
          properties:
            device_id:
              type: string
              description: Unique identifier for the device
            user_id:
              type: string
              description: Identifier for the user associated with the device
    responses:
        200:
            description: Device registered successfully
        400:
            description: Invalid input
        500:
            description: Internal server error
    """
    data = request.get_json()
    db = DBConnector.get_db()
    
    if db is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    if not data:
        return jsonify({"error": "Invalid input, JSON data is required"}), 400
    
    if not isinstance(data.get('device_id'), str) or not isinstance(data.get('user_id'), str):
        return jsonify({"error": "Invalid input types: device_id and user_id must be strings"}), 400
    
    device_id = data.get('device_id')
    user_id = data.get('user_id')
    
    db.registered_devices.insert_one({
        "device_id": device_id,
        "user_id": user_id
    })
    
    return jsonify({"message": "Device registered successfully", "device": {
        "device_id": device_id,
        "user_id": user_id
    }}), 200

@in_app_notifications_bp.route('/api/v1/sdk/notifications', methods=['GET'])
def get_notifications():
    """Get in-app notifications for a user
    ---
    tags:
      - In-App Notifications - SDK 
    parameters:
      - name: user_id
        in: query
        required: true
        type: string
        description: Identifier for the user to retrieve notifications for
    responses:
        200:
            description: Notifications retrieved successfully
        400:
            description: Invalid input
        500:
            description: Internal server error
    """
    user_id = request.args.get('user_id')
    db = DBConnector.get_db()
    
    if db is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    if not user_id:
        return jsonify({"error": "Invalid input, user_id is required"}), 400
    
    notifications = list(db.notifications.find({"user_id": user_id}))
    
    # Convert ObjectId to string for JSON serialization
    for note in notifications:
        note['_id'] = str(note['_id'])
    
    return jsonify({"message": "Notifications retrieved successfully", "notifications": notifications}), 200

@in_app_notifications_bp.route('/api/v1/sdk/sync', methods=['POST'])
def sync_notifications():
    """Sync in-app notifications for a user
    ---
    tags:
      - In-App Notifications - SDK 
    parameters:
      - name: user_id
        in: body
        required: true
        description: Identifier for the user to sync notifications for
        schema:
          type: object
          required:
            - user_id
          properties:
            user_id:
              type: string
              description: Identifier for the user to sync notifications for
    responses:
        200:
            description: Notifications synced successfully
        400:
            description: Invalid input
        500:
            description: Internal server error
    """
    data = request.get_json()
    db = DBConnector.get_db()
    
    if db is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    if not data:
        return jsonify({"error": "Invalid input, JSON data is required"}), 400
    
    if not isinstance(data.get('user_id'), str):
        return jsonify({"error": "Invalid input type: user_id must be a string"}), 400
    
    user_id = data.get('user_id')
    
    return jsonify({"message": "Notifications synced successfully", "user_id": user_id}), 200

@in_app_notifications_bp.route('/api/v1/sdk/crash-report', methods=['POST'])
def report_crash():
    """Report a crash for in-app notifications
    ---
    tags:
      - In-App Notifications - SDK 
    parameters:
      - name: crash_info
        in: body
        required: true
        description: Crash information for reporting
        schema:
          type: object
          required:
            - user_id
            - crash_details
          properties:
            user_id:
              type: string
              description: Identifier for the user who experienced the crash
            crash_details:
              type: string
              description: Details about the crash (e.g., error message, stack trace)
    responses:
        200:
            description: Crash reported successfully
        400:
            description: Invalid input
        500:
            description: Internal server error
    """
    data = request.get_json()
    db = DBConnector.get_db()
    
    if db is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    if not data:
        return jsonify({"error": "Invalid input, JSON data is required"}), 400
    
    if not isinstance(data.get('user_id'), str) or not isinstance(data.get('crash_details'), str):
        return jsonify({"error": "Invalid input types: user_id and crash_details must be strings"}), 400
    
    user_id = data.get('user_id')
    crash_details = data.get('crash_details')
    
    db.crash_reports.insert_one({
        "user_id": user_id,
        "crash_details": crash_details
    })
    
    return jsonify({"message": "Crash reported successfully", "crash_report": {
        "user_id": user_id,
        "crash_details": crash_details
    }}), 200

@in_app_notifications_bp.route('/api/v1/admin/campaigns', methods=['GET'])
def get_campaigns():
    """Get all in-app notification campaigns
    ---
    tags:
      - In-App Notifications - portal
    responses:
        200:
            description: Campaigns retrieved successfully
        500:
            description: Internal server error
    """
    db = DBConnector.get_db()
    
    if db is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    campaigns = list(db.campaigns.find())
    
    # Convert ObjectId to string for JSON serialization
    for camp in campaigns:
        camp['_id'] = str(camp['_id'])
    
    return jsonify({"message": "Campaigns retrieved successfully", "campaigns": campaigns}), 200

@in_app_notifications_bp.route('/api/v1/admin/campaigns', methods=['POST'])
def create_campaign():
    """Create a new in-app notification campaign
    ---
    tags:
      - In-App Notifications - Campaign Management
    parameters:
      - name: campaign_info
        in: body
        required: true
        description: Information for creating a new campaign
        schema:
          type: object
          required:
            - name
            - message
          properties:
            name:
              type: string
              description: Name of the campaign
            message:
              type: string
              description: Message content for the campaign
    responses:
        200:
            description: Campaign created successfully
        400:
            description: Invalid input
        500:
            description: Internal server error
    """
    data = request.get_json()
    db = DBConnector.get_db()
    
    if db is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    if not data:
        return jsonify({"error": "Invalid input, JSON data is required"}), 400
    
    if not isinstance(data.get('name'), str) or not isinstance(data.get('message'), str):
        return jsonify({"error": "Invalid input types: name and message must be strings"}), 400
    
    name = data.get('name')
    message = data.get('message')
    
    result = db.campaigns.insert_one({
        "name": name,
        "message": message
    })
    
    return jsonify({"message": "Campaign created successfully", "campaign": {
        "_id": str(result.inserted_id),
        "name": name,
        "message": message
    }}), 200

@in_app_notifications_bp.route('/api/v1/admin/campaigns/<campaign_id>', methods=['DELETE'])
def delete_campaign(campaign_id):
    """Delete an in-app notification campaign
    ---
    tags:
      - In-App Notifications - portal
    parameters:
      - name: campaign_id
        in: path
        required: true
        type: string
        description: Identifier for the campaign to delete
    responses:
        200:
            description: Campaign deleted successfully
        400:
            description: Invalid input
        404:
            description: Campaign not found
        500:
            description: Internal server error
    """
    db = DBConnector.get_db()
    
    if db is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    if not campaign_id:
        return jsonify({"error": "Invalid input, campaign_id is required"}), 400
        
    try:
        obj_id = ObjectId(campaign_id)
    except InvalidId:
        return jsonify({"error": "Invalid campaign_id format"}), 400
    
    result = db.campaigns.delete_one({"_id": obj_id})
    
    if result.deleted_count == 0:
        return jsonify({"error": "Campaign not found"}), 404
    
    return jsonify({"message": "Campaign deleted successfully", "campaign_id": campaign_id}), 200

@in_app_notifications_bp.route('/api/v1/admin/campaigns/<campaign_id>/status', methods=['PATCH'])
def update_campaign_status(campaign_id):
    """Update the status of an in-app notification campaign
    ---
    tags:
      - In-App Notifications - portal
    parameters:
      - name: campaign_id
        in: path
        required: true
        type: string
        description: Identifier for the campaign to update
      - name: status_info
        in: body
        required: true
        description: New status for the campaign
        schema:
          type: object
          required:
            - status
          properties:
            status:
              type: string
              description: New status for the campaign (e.g., active, paused)
    responses:
        200:
            description: Campaign status updated successfully
        400:
            description: Invalid input
        404:
            description: Campaign not found
        500:
            description: Internal server error
    """
    data = request.get_json()
    db = DBConnector.get_db()
    
    if db is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    if not data:
        return jsonify({"error": "Invalid input, JSON data is required"}), 400
    
    if not isinstance(data.get('status'), str):
        return jsonify({"error": "Invalid input type: status must be a string"}), 400
        
    try:
        obj_id = ObjectId(campaign_id)
    except InvalidId:
        return jsonify({"error": "Invalid campaign_id format"}), 400
    
    status = data.get('status')
    
    result = db.campaigns.update_one({"_id": obj_id}, {"$set": {"status": status}})
    
    if result.matched_count == 0:
        return jsonify({"error": "Campaign not found"}), 404
    
    return jsonify({"message": "Campaign status updated successfully", "campaign_id": campaign_id, "new_status": status}), 200

@in_app_notifications_bp.route('/api/v1/admin/campaigns/test-push', methods=['POST'])
def send_test_push():
    """Send a test push notification for an in-app notification campaign
    ---
    tags:
      - In-App Notifications - portal
    parameters:
      - name: test_push_info
        in: body
        required: true
        description: Information for sending a test push notification
        schema:
          type: object
          required:
            - campaign_id
            - user_id
          properties:
            campaign_id:
              type: string
              description: Identifier for the campaign to test
            user_id:
              type: string
              description: Identifier for the user to receive the test push notification
    responses:
        200:
            description: Test push notification sent successfully
        400:
            description: Invalid input
        500:
            description: Internal server error
    """ 
    data = request.get_json()
    db = DBConnector.get_db()
    
    if db is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    if not data:
        return jsonify({"error": "Invalid input, JSON data is required"}), 400
    
    if not isinstance(data.get('campaign_id'), str) or not isinstance(data.get('user_id'), str):
        return jsonify({"error": "Invalid input types: campaign_id and user_id must be strings"}), 400
    
    campaign_id = data.get('campaign_id')
    user_id = data.get('user_id')
    
    return jsonify({"message": "Test push notification sent successfully", "test_push_info": {
        "campaign_id": campaign_id,
        "user_id": user_id
    }}), 200

@in_app_notifications_bp.route('/api/v1/admin/stats/overview', methods=['GET'])
def get_overview_stats():
    """Get overview statistics for in-app notifications
    ---
    tags:
      - In-App Notifications - portal
    responses:
        200:
            description: Overview statistics retrieved successfully
        500:
            description: Internal server error 
    """
    db = DBConnector.get_db()
    
    if db is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    stats = {
        "total_notifications_sent": db.notifications.count_documents({}),
        "total_active_campaigns": db.campaigns.count_documents({"status": "active"}),
    }
    
    return jsonify({"message": "Overview statistics retrieved successfully", "stats": stats}), 200

@in_app_notifications_bp.route('/api/v1/admin/stats/campaign/<campaign_id>', methods=['GET'])
def get_campaign_stats(campaign_id):
    """Get statistics for a specific in-app notification campaign
    ---
    tags:
      - In-App Notifications - portal
    parameters:
      - name: campaign_id
        in: path
        required: true
        type: string
        description: Identifier for the campaign to retrieve statistics for
    responses:
        200:
            description: Campaign statistics retrieved successfully
        400:
            description: Invalid input
        500:
            description: Internal server error
    """
    db = DBConnector.get_db()
    
    if db is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    if not campaign_id:
        return jsonify({"error": "Invalid input, campaign_id is required"}), 400
        
    try:
        obj_id = ObjectId(campaign_id)
    except InvalidId:
        return jsonify({"error": "Invalid campaign_id format"}), 400
    
    stats = {
        # Using obj_id or campaign_id string depending on how you store foreign keys
        "total_notifications_sent": db.notifications.count_documents({"campaign_id": campaign_id}),
        "total_clicks": db.notifications.count_documents({"campaign_id": campaign_id, "clicked": True}),
    }
    
    return jsonify({"message": "Campaign statistics retrieved successfully", "campaign_id": campaign_id, "stats": stats}), 200