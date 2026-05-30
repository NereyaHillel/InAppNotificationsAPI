from dotenv import load_dotenv
from pymongo import MongoClient
import os

DB_CONNECTION_STRING=os.getenv('DB_CONNECTION_STRING')
DB_NAME=os.getenv('DB_NAME')
DB_USER=os.getenv('DB_USER')
DB_PASSWORD=os.getenv('DB_PASSWORD')

MONGODB_URI = f"mongodb+srv://{DB_USER}:{DB_PASSWORD}@{DB_CONNECTION_STRING}/{DB_NAME}"


load_dotenv()

class DBConnector:
    __db = None

    @staticmethod
    def initialize_db():
        if DBConnector.__db is None:
            try:
                client = MongoClient(MONGODB_URI)
                DBConnector.__db = client[DB_NAME]
                # Test the connection by listing collections
                DBConnector.__db.list_collection_names()
                print("Database connection established successfully.")
                DBConnector.__db = client[DB_NAME]
            except Exception as e:
                print(f"Failed to connect to the database: {e}")
                DBConnector.__db = None
        return DBConnector.__db
    
    @staticmethod
    def get_db():
        if DBConnector.__db is None:
            DBConnector.initialize_db()
        return DBConnector.__db