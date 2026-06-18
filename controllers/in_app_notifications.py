import uuid
from flask import Blueprint, request, jsonify, abort, make_response
from DB_Connector import DBConnector

in_app_notifications_bp = Blueprint('in_app_notifications_bp', __name__)

# ==========================================
# HELPER FUNCTIONS (Professional DRY Logic)
# ==========================================

def _get_db():
    """Returns the DB instance or instantly aborts the route with a 500 error."""
    db = DBConnector.get_db()
    if db is None:
        abort(make_response(jsonify({"error": "Database connection failed"}), 500))
    return db

def _get_valid_json(required_fields=None):
    """Fetches JSON, validates required fields exist as strings, or aborts with 400."""
    data = request.get_json()
    if not data:
        abort(make_response(jsonify({"error": "Invalid input, JSON data is required"}), 400))
        
    if required_fields:
        missing_or_invalid = [
            f for f in required_fields 
            if not isinstance(data.get(f), str) or not str(data.get(f)).strip()
        ]
        if missing_or_invalid:
            err_msg = f"Invalid input: '{', '.join(missing_or_invalid)}' must be valid, non-empty strings."
            abort(make_response(jsonify({"error": err_msg}), 400))
            
    return data

def _distribute_campaigns(db, campaigns, user_ids):
    """
    Highly optimized bulk distributor. Compares requested campaigns/users 
    against the DB in a single batch query to prevent N+1 bottleneck crashes.
    """
    if not campaigns or not user_ids:
        return
        
    c_ids = [str(c['_id']) for c in campaigns]
    
    # 1. Fetch all existing pairs in one single network call
    existing_cursor = db.notifications.find(
        {"campaign_id": {"$in": c_ids}, "user_id": {"$in": user_ids}},
        {"campaign_id": 1, "user_id": 1, "_id": 0}
    )
    existing_pairs = {(doc["campaign_id"], doc["user_id"]) for doc in existing_cursor}
    
    # 2. Build list of missing notifications in memory
    notifications_to_insert = []
    for campaign in campaigns:
        cid = str(campaign['_id'])
        for uid in user_ids:
            if (cid, uid) not in existing_pairs:
                notifications_to_insert.append({
                    "_id": uuid.uuid4().hex,
                    "campaign_id": cid,
                    "user_id": uid,
                    "title": campaign.get("name"),
                    "message": campaign.get("message"),
                    "status": "delivered",
                    "clicked": False
                })
                
    # 3. Insert all at once
    if notifications_to_insert:
        db.notifications.insert_many(notifications_to_insert)

# ==========================================
# ROUTES
# ==========================================

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
            - device_name
            - device_id
            - user_id
          properties:
            device_name:
              type: string
              description: Name of the device
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
    db = _get_db()
    data = _get_valid_json(['device_id', 'user_id'])
    
    device_id = data.get('device_id')
    user_id = data.get('user_id')
    
    db.registered_devices.update_one(
        {"device_id": device_id}, 
        {"$set": {"user_id": user_id, "last_active": "..."}}, 
        upsert=True 
    )
    
    active_campaigns = list(db.campaigns.find({"status": "active"}))
    _distribute_campaigns(db, active_campaigns, [user_id])
            
    return jsonify({"message": "Device registered successfully", "device": {
        "device_id": device_id,
        "user_id": user_id
    }}), 200

@in_app_notifications_bp.route('/api/v1/sdk/notifications', methods=['GET'])
def get_notifications():
    """Get unread in-app notifications for a user
    ---
    tags:
      - In-App Notifications - SDK 
    parameters:
      - name: user_id
        in: query
        required: true
        type: string
        description: Identifier for the user to retrieve unread notifications for
    responses:
        200:
            description: Unread notifications retrieved successfully
        400:
            description: Invalid input
        500:
            description: Internal server error
    """
    db = _get_db()
    user_id = request.args.get('user_id')
    
    if not user_id or not user_id.strip():
        abort(make_response(jsonify({"error": "Invalid input, user_id query parameter is required"}), 400))
    
    query = {
        "user_id": user_id,
        "status": {"$ne": "read"} 
    }
    
    notifications = list(db.notifications.find(query))
    for note in notifications:
        note['_id'] = str(note['_id'])
    
    return jsonify({
        "message": "Unread notifications retrieved successfully", 
        "notifications": notifications
    }), 200

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
    db = _get_db()
    data = _get_valid_json(['user_id'])
    return jsonify({"message": "Notifications synced successfully", "user_id": data.get('user_id')}), 200

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
    db = _get_db()
    data = _get_valid_json(['user_id', 'crash_details'])
    
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
    
@in_app_notifications_bp.route('/api/v1/sdk/notifications/<id>/interact', methods=['POST'])
def interact_with_notification(id):
    """
    Mark a specific in-app notification as read and track clicks
    ---
    tags:
      - SDK Notifications
    summary: Track user interaction with a notification
    description: Marks the notification status as 'read' so it won't be shown again. If the action is 'clicked', it also updates the click status to true for analytics tracking.
    parameters:
      - name: id
        in: path
        type: string
        required: true
        description: The unique hexadecimal or UUID string identifying the notification.
        example: "08ecc229e9354d41a0cd634c59178e93"
      - name: action
        in: query
        type: string
        required: false
        default: dismissed
        enum: [clicked, dismissed]
        description: The explicit interaction behavior executed by the client application.
        example: "clicked"
    responses:
      200:
        description: Interaction successfully recorded and state updated in the database.
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Notification interaction tracked successfully"
            notification_id:
              type: string
              example: "08ecc229e9354d41a0cd634c59178e93"
            action:
              type: string
              example: "clicked"
      400:
        description: Bad Request. The notification ID parameter was missing or consisted only of whitespace.
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Invalid input, notification ID is required in the path"
      404:
        description: Not Found. No notification document matched the provided ID string in the database collection.
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Notification not found"
    """
    db = _get_db()
    
    action = request.args.get('action', 'dismissed')
    
    if not id or not id.strip():
        abort(make_response(jsonify({"error": "Invalid input, notification ID is required in the path"}), 400))
    
    update_data = {"status": "read"}
    
    if action == "clicked":
        update_data["clicked"] = True
        
    result = db.notifications.update_one(
        {"_id": id}, 
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        abort(make_response(jsonify({"error": "Notification not found"}), 404))
    
    return jsonify({
        "message": "Notification interaction tracked successfully", 
        "notification_id": id,
        "action": action
    }), 200

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
    db = _get_db()
    campaigns = list(db.campaigns.find())
    
    for camp in campaigns:
        camp['_id'] = str(camp['_id'])
    
    return jsonify({"message": "Campaigns retrieved successfully", "campaigns": campaigns}), 200

@in_app_notifications_bp.route('/api/v1/admin/campaigns', methods=['POST'])
def create_campaign():
    """Create a new in-app notification campaign
    ---
    tags:
      - In-App Notifications - portal
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
            - status
            - position (e.g., top, bottom, center)
          properties:
            name:
              type: string
              description: Name of the campaign
            message:
              type: string
              description: Message content for the campaign
            status:
              type: string
              description: Status of the campaign (e.g., active, paused)
            position:
              type: string
              description: Position of the campaign (e.g., top, bottom, center)
    responses:
        200:
            description: Campaign created successfully
        400:
            description: Invalid input
        500:
            description: Internal server error
    """
    db = _get_db()
    data = _get_valid_json(['name', 'message'])
    
    name = data.get('name')
    message = data.get('message')
    status = data.get('status') if data.get('status') else "draft"
    position = data.get('position') if data.get('position') else "center"
    
    campaign_doc = {
        "_id": uuid.uuid4().hex,
        "name": name,
        "message": message,
        "status": status,
        "position": position
    }
    
    db.campaigns.insert_one(campaign_doc)
    
    if status == "active":
        users = db.registered_devices.distinct("user_id")
        _distribute_campaigns(db, [campaign_doc], users)
    
    return jsonify({"message": "Campaign created successfully", "campaign": campaign_doc}), 200

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
    db = _get_db()
    
    if not campaign_id or not campaign_id.strip():
        abort(make_response(jsonify({"error": "Invalid input, campaign_id is required"}), 400))
        
    result = db.campaigns.delete_one({"_id": campaign_id})
    if result.deleted_count == 0:
        abort(make_response(jsonify({"error": "Campaign not found"}), 404))
    
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
            description: Campaign status updated successfully (and notifications generated if active)
        400:
            description: Invalid input
        404:
            description: Campaign not found
        500:
            description: Internal server error
    """
    db = _get_db()
    data = _get_valid_json(['status'])
    status = data.get('status')
    
    result = db.campaigns.update_one({"_id": campaign_id}, {"$set": {"status": status}})
    if result.matched_count == 0:
        abort(make_response(jsonify({"error": "Campaign not found"}), 404))

    if status == "active":
        campaign = db.campaigns.find_one({"_id": campaign_id})
        users = db.registered_devices.distinct("user_id")
        _distribute_campaigns(db, [campaign], users)
    
    return jsonify({
        "message": f"Campaign status updated to {status}", 
        "campaign_id": campaign_id, 
        "new_status": status
    }), 200

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
    db = _get_db()
    data = _get_valid_json(['campaign_id', 'user_id'])
    
    return jsonify({
        "message": "Test push notification sent successfully", 
        "test_push_info": {
            "campaign_id": data.get('campaign_id'),
            "user_id": data.get('user_id')
        }
    }), 200

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
    db = _get_db()
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
    db = _get_db()
    
    if not campaign_id or not campaign_id.strip():
        abort(make_response(jsonify({"error": "Invalid input, campaign_id is required"}), 400))
        
    stats = {
        "total_notifications_sent": db.notifications.count_documents({"campaign_id": campaign_id}),
        "total_clicks": db.notifications.count_documents({"campaign_id": campaign_id, "clicked": True}),
    }
    
    return jsonify({
        "message": "Campaign statistics retrieved successfully", 
        "campaign_id": campaign_id, 
        "stats": stats
    }), 200