import uuid
import logging
import datetime
from flask import Blueprint, request, jsonify, abort, make_response
from DB_Connector import DBConnector
from bson import ObjectId

logger = logging.getLogger(__name__)

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
            - device_model
            - device_id
            - user_id
          properties:
            device_model:
              type: string
              description: Model of the device
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
    data = _get_valid_json(['device_id', 'user_id', 'device_model'])
    
    device_model = data.get('device_model')
    device_id = data.get('device_id')
    user_id = data.get('user_id')
    
    db.registered_devices.update_one(
        {"device_id": device_id}, 
        {"$set": {"device_model": device_model, "user_id": user_id}}, 
        upsert=True 
    )
    
    logger.info(f"Device registered: user_id={user_id}, device_id={device_id}")
    
    active_campaigns = list(db.campaigns.find({"status": "active"}))
    _distribute_campaigns(db, active_campaigns, [user_id])
            
    return jsonify({"message": "Device registered successfully"}), 200

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
    if notifications:
        # Extract campaign IDs and convert to ObjectId for proper MongoDB lookup
        campaign_ids = list({n['campaign_id'] for n in notifications})
        
        # Try to convert campaign_ids to ObjectId, but handle both string and ObjectId formats
        campaign_object_ids = []
        for cid in campaign_ids:
            try:
                if isinstance(cid, str):
                    campaign_object_ids.append(ObjectId(cid))
                else:
                    campaign_object_ids.append(cid)
            except:
                campaign_object_ids.append(cid)
        
        # Query campaigns by ObjectId
        campaigns = list(db.campaigns.find({"_id": {"$in": campaign_object_ids}}))
        campaigns_map = {str(c['_id']): c for c in campaigns}
        
        logger.info(f"Found {len(campaigns)} campaigns for {len(notifications)} notifications")
        logger.debug(f"Campaign IDs: {campaign_ids}")
        logger.debug(f"Campaigns map keys: {list(campaigns_map.keys())}")
        
        for note in notifications:
            camp = campaigns_map.get(note['campaign_id'], {})
            if not camp:
                logger.warning(f"Campaign not found for notification {note['_id']}, campaign_id: {note['campaign_id']}")
            
            note['title'] = camp.get('name', '')
            note['message'] = camp.get('message', '')
            note['position'] = camp.get('position')
            note['image_url'] = camp.get('image_url')
            note['link'] = camp.get('link')
            note['btn_positive'] = camp.get('btn_positive')
            note['btn_negative'] = camp.get('btn_negative')
            note['btn_neutral'] = camp.get('btn_neutral')
            note['_id'] = str(note['_id'])
            
            # Debug log
            logger.debug(f"Notification {note['_id']}: position={note.get('position')}, btn_positive={note.get('btn_positive')}")
    
    logger.info(f"Retrieved {len(notifications)} unread notifications for user_id={user_id}")
    
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
    
    crash_id = uuid.uuid4().hex
    db.crash_reports.insert_one({
        "_id": crash_id,
        "user_id": user_id,
        "crash_details": crash_details,
        "created_at": datetime.datetime.utcnow()
    })
    
    logger.error(f"Crash reported by user_id={user_id}, crash_id={crash_id}")
    
    return jsonify({"message": "Crash reported successfully"}), 200
    
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
    
    update_data = {"status": "read", "expires_at": datetime.datetime.utcnow() + datetime.timedelta(days=90)}

    if action == "clicked":
        update_data["clicked"] = True
        
    result = db.notifications.update_one(
        {"_id": id}, 
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        abort(make_response(jsonify({"error": "Notification not found"}), 404))
    
    logger.info(f"Notification interaction tracked: notification_id={id}, action={action}")
    
    return jsonify({
        "message": "Notification interaction tracked successfully"
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
          properties:
            name:
              type: string
              description: Name of the campaign
            message:
              type: string
              description: Message content for the campaign (optional)
            status:
              type: string
              description: Status of the campaign (e.g., active, draft, paused)
            position:
              type: string
              description: SDUI display position (e.g., TOP, BOTTOM, CENTER)
              example: TOP
            image_url:
              type: string
              description: Optional URL of the image to display in the notification
            link:
              type: string
              description: Optional deep link or web URL to open on interaction
            btn_positive:
              type: string
              description: Optional label for the positive action button
            btn_negative:
              type: string
              description: Optional label for the negative action button
            btn_neutral:
              type: string
              description: Optional label for the neutral action button
    responses:
        200:
            description: Campaign created successfully
        400:
            description: Invalid input
        500:
            description: Internal server error
    """
    db = _get_db()
    data = _get_valid_json(['name'])
    
    name = data.get('name')
    message = data.get('message')
    status = data.get('status') if data.get('status') else "draft"

    campaign_doc = {
        "_id": uuid.uuid4().hex,
        "name": name,
        "message": message,
        "status": status,
        "position": data.get('position') or None,
        "image_url": data.get('image_url') or None,
        "link": data.get('link') or None,
        "btn_positive": data.get('btn_positive') or None,
        "btn_negative": data.get('btn_negative') or None,
        "btn_neutral": data.get('btn_neutral') or None,
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


@in_app_notifications_bp.route('/api/v1/admin/stats/dashboard', methods=['GET'])
def get_dashboard_stats():
    """
    Get dashboard statistics and campaign summary for the admin dashboard
    ---
    tags:
      - In-App Notifications - portal
    summary: Retrieve overall campaign analytics and chart data
    description: Returns aggregated dashboard metrics along with campaign-level summary and chart datasets for dashboard rendering.
    responses:
      200:
        description: Dashboard statistics retrieved successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Dashboard statistics retrieved successfully
            stats:
              type: object
              properties:
                total_notifications_sent:
                  type: integer
                  example: 12
                total_active_campaigns:
                  type: integer
                  example: 3
                open_rate:
                  type: number
                  format: float
                  example: 52.4
                click_rate:
                  type: number
                  format: float
                  example: 18.7
            campaign_summary:
              type: array
              items:
                type: object
                properties:
                  campaign_id:
                    type: string
                    example: '868c0fe6d66346d0a40378ca8a0ae9e4'
                  name:
                    type: string
                    example: 'My First Test Campaign'
                  status:
                    type: string
                    example: 'draft'
                  sent:
                    type: integer
                    example: 5
                  opened:
                    type: integer
                    example: 3
                  open_rate:
                    type: number
                    format: float
                    example: 60.0
                  click_rate:
                    type: number
                    format: float
                    example: 20.0
                  clicked:
                    type: integer
                    example: 1
            chart_data:
              type: object
              properties:
                labels:
                  type: array
                  items:
                    type: string
                  example: ['Campaign A (active)', 'Campaign B (draft)']
                sent:
                  type: array
                  items:
                    type: integer
                  example: [3, 0]
                open_rates:
                  type: array
                  items:
                    type: number
                  example: [33.3, 0.0]
                click_rates:
                  type: array
                  items:
                    type: number
                  example: [0.0, 0.0]
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Database connection failed
    """
    db = _get_db()

    notif_agg = list(db.notifications.aggregate([{"$group": {
        "_id": None,
        "total": {"$sum": 1},
        "opened": {"$sum": {"$cond": [{"$eq": ["$status", "read"]}, 1, 0]}},
        "clicked": {"$sum": {"$cond": [{"$eq": ["$clicked", True]}, 1, 0]}}
    }}]))
    ns = notif_agg[0] if notif_agg else {"total": 0, "opened": 0, "clicked": 0}
    total_notifications_sent = ns["total"]
    total_opened = ns["opened"]
    total_clicked = ns["clicked"]
    total_active_campaigns = db.campaigns.count_documents({"status": "active"})

    open_rate = round((total_opened / total_notifications_sent) * 100, 1) if total_notifications_sent else 0.0
    click_rate = round((total_clicked / total_notifications_sent) * 100, 1) if total_notifications_sent else 0.0

    pipeline = [
        {"$group": {
            "_id": "$campaign_id",
            "sent": {"$sum": 1},
            "opened": {"$sum": {"$cond": [{"$eq": ["$status", "read"]}, 1, 0]}},
            "clicked": {"$sum": {"$cond": [{"$eq": ["$clicked", True]}, 1, 0]}}
        }},
        {"$sort": {"sent": -1}},
        {"$limit": 4}
    ]

    campaign_stats = list(db.notifications.aggregate(pipeline))
    stats_by_campaign = {stat["_id"]: stat for stat in campaign_stats}
    campaigns = list(db.campaigns.find())

    campaign_summary = []
    chart_labels = []
    chart_sent = []
    chart_open_rate = []
    chart_click_rate = []

    for campaign in campaigns:
        campaign_id = str(campaign["_id"])
        stat = stats_by_campaign.get(campaign_id, {"sent": 0, "opened": 0, "clicked": 0})
        open_rate_campaign = round((stat["opened"] / stat["sent"]) * 100, 1) if stat["sent"] else 0.0
        click_rate_campaign = round((stat["clicked"] / stat["sent"]) * 100, 1) if stat["sent"] else 0.0
        label = f"{campaign.get('name', 'Unknown')} ({campaign.get('status', 'unknown')})"

        campaign_summary.append({
            "campaign_id": campaign_id,
            "name": campaign.get("name", "Unknown"),
            "status": campaign.get("status", "unknown"),
            "sent": stat["sent"],
            "opened": stat["opened"],
            "open_rate": open_rate_campaign,
            "click_rate": click_rate_campaign,
            "clicked": stat["clicked"]
        })

        chart_labels.append(label)
        chart_sent.append(stat["sent"])
        chart_open_rate.append(open_rate_campaign)
        chart_click_rate.append(click_rate_campaign)

    return jsonify({
        "message": "Dashboard statistics retrieved successfully",
        "stats": {
            "total_notifications_sent": total_notifications_sent,
            "total_active_campaigns": total_active_campaigns,
            "open_rate": open_rate,
            "click_rate": click_rate
        },
        "campaign_summary": campaign_summary,
        "chart_data": {
            "labels": chart_labels,
            "sent": chart_sent,
            "open_rates": chart_open_rate,
            "click_rates": chart_click_rate
        }
    }), 200

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