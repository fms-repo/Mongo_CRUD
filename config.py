from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError
import logging

# Enable logging for debugging
logging.basicConfig(level=logging.INFO)

# MongoDB Configuration
MONGODB_USERNAME = "admin"
MONGODB_PASSWORD = "admin123"
MONGODB_HOST = "localhost"
MONGODB_PORT = 27017
MONGODB_DATABASE = "mydb"

# MongoDB Connection String
MONGODB_URL = f"mongodb://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/"
print(MONGODB_URL)

# Global MongoDB client (will be initialized on startup)
_client: AsyncIOMotorClient = None
_database = None


def get_mongodb_client() -> AsyncIOMotorClient:
    """Get MongoDB async client"""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            MONGODB_URL,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=10
        )
    return _client


def get_database():
    """Get MongoDB database instance"""
    global _database
    if _database is None:
        client = get_mongodb_client()
        _database = client[MONGODB_DATABASE]
    return _database


async def close_mongodb_connection():
    """Close MongoDB connection on application shutdown"""
    global _client
    if _client:
        _client.close()
        _client = None