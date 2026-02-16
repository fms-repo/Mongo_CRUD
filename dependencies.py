from config import get_database

async def get_db():
    """Dependency to get MongoDB database"""
    return get_database()