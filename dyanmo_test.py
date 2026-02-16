import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure

print("Testing direct MongoDB connection...\n")

# Configuration
MONGODB_URL = "mongodb://admin:admin123@localhost:27017/"
DATABASE_NAME = "mydb"

async def test_mongodb():
    try:
        # Create client
        client = AsyncIOMotorClient(
            MONGODB_URL,
            serverSelectionTimeoutMS=5000
        )
        
        # Test connection
        print("1. Testing connection...")
        await client.admin.command('ping')
        print("✅ SUCCESS! Connected to MongoDB")
        
        # Get database
        db = client[DATABASE_NAME]
        
        # List collections
        print("\n2. Listing collections...")
        collections = await db.list_collection_names()
        print(f"✅ Collections: {collections}")
        
        # Try to create a test collection
        print("\n3. Creating test collection...")
        test_collection = db['TestCollection']
        try:
            # Insert a test document (collection is created automatically)
            result = await test_collection.insert_one({"name": "test", "value": 123})
            print(f"✅ Test document inserted with ID: {result.inserted_id}")
        except Exception as e:
            print(f"⚠️ Error creating test document: {e}")
        
        # List collections again
        print("\n4. Listing collections again...")
        collections = await db.list_collection_names()
        user_collections = [c for c in collections if not c.startswith('system.')]
        print(f"✅ Collections: {user_collections}")
        
        # Count documents in test collection
        print("\n5. Counting documents in TestCollection...")
        count = await test_collection.count_documents({})
        print(f"✅ Document count: {count}")
        
        print("\n" + "="*50)
        print("✅ MongoDB connection works perfectly!")
        print("The MongoDB setup is working correctly")
        
        # Close connection
        client.close()
        
    except ConnectionFailure as e:
        print(f"❌ FAILED: Connection error")
        print(f"Error: {str(e)}")
        print("\n" + "="*50)
        print("MongoDB connection failed! Make sure MongoDB is running.")
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}")
        print(f"Error: {str(e)}")
        print("\n" + "="*50)
        print("MongoDB test failed!")

if __name__ == "__main__":
    asyncio.run(test_mongodb())