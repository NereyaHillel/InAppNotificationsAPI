try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from pymongo import MongoClient
import os
import logging

logger = logging.getLogger(__name__)

if load_dotenv:
    load_dotenv()
else:
    logger.warning('python-dotenv is not installed; .env will not be loaded automatically.')

DB_CONNECTION_STRING = os.getenv('DB_CONNECTION_STRING')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
MONGODB_URI = os.getenv('MONGODB_URI')

if not MONGODB_URI:
    if DB_USER and DB_PASSWORD and DB_CONNECTION_STRING and DB_NAME:
        MONGODB_URI = f"mongodb+srv://{DB_USER}:{DB_PASSWORD}@{DB_CONNECTION_STRING}/{DB_NAME}"
    else:
        logger.warning('one or more MongoDB environment variables are missing. Set MONGODB_URI or DB_USER, DB_PASSWORD, DB_CONNECTION_STRING, and DB_NAME.')

class DBConnector:
    __db = None

    @staticmethod
    def initialize_db():
        if DBConnector.__db is None:
            if not MONGODB_URI:
                logger.error('Database initialization failed: missing MongoDB URI.')
                return None

            try:
                client = MongoClient(MONGODB_URI)
                DBConnector.__db = client[DB_NAME]
                # Test the connection by listing collections
                DBConnector.__db.list_collection_names()
                DBConnector._ensure_indexes(DBConnector.__db)
                logger.info("Database connection established successfully.")
            except Exception as e:
                logger.error(f"Failed to connect to the database: {e}")
                DBConnector.__db = None
        return DBConnector.__db
    
    @staticmethod
    def _ensure_indexes(db):
        from pymongo import ASCENDING
        # Compound index: main SDK read query (user_id + status)
        db.notifications.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
        # Compound index: dedup check in _distribute_campaigns
        db.notifications.create_index([("campaign_id", ASCENDING), ("user_id", ASCENDING)])
        # TTL index: auto-delete read notifications after their expires_at date
        db.notifications.create_index("expires_at", expireAfterSeconds=0, sparse=True)
        # TTL index: auto-delete crash reports after 30 days
        db.crash_reports.create_index("created_at", expireAfterSeconds=2592000)
        # Index: campaign status filter
        db.campaigns.create_index("status")

    @staticmethod
    def get_db():
        if DBConnector.__db is None:
            DBConnector.initialize_db()
        return DBConnector.__db