from fastapi import APIRouter, HTTPException, Depends
from pymongo.errors import PyMongoError, CollectionInvalid
from dependencies import get_db
from models import CreateCollectionRequest, CollectionResponse

router = APIRouter(prefix="/admin/collections", tags=["Collection Management"])


@router.post("/", response_model=CollectionResponse, status_code=201)
async def create_collection(
    request: CreateCollectionRequest,
    db = Depends(get_db)
):
    """Create a new MongoDB collection"""
    try:
        # Check if collection already exists
        existing_collections = await db.list_collection_names()
        if request.collection_name in existing_collections:
            raise HTTPException(status_code=400, detail="Collection already exists")
        
        # Create collection (MongoDB creates it implicitly, but we can create explicitly)
        await db.create_collection(request.collection_name)
        
        return CollectionResponse(
            message="Collection created successfully",
            collection_name=request.collection_name,
            status="active"
        )
        
    except CollectionInvalid as e:
        raise HTTPException(status_code=400, detail=f"Invalid collection name: {str(e)}")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_collections(db = Depends(get_db)):
    """List all collections in MongoDB"""
    try:
        collections = await db.list_collection_names()
        # Filter out system collections
        user_collections = [c for c in collections if not c.startswith('system.')]
        return {
            "collections": user_collections,
            "count": len(user_collections)
        }
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{collection_name}")
async def describe_collection(
    collection_name: str,
    db = Depends(get_db)
):
    """Get detailed information about a specific collection"""
    try:
        # Check if collection exists
        existing_collections = await db.list_collection_names()
        if collection_name not in existing_collections:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        collection = db[collection_name]
        
        # Get collection stats
        stats = await db.command("collStats", collection_name)
        document_count = await collection.count_documents({})
        
        return {
            "collection_name": collection_name,
            "status": "active",
            "document_count": document_count,
            "size_bytes": stats.get("size", 0),
            "storage_size_bytes": stats.get("storageSize", 0),
            "index_count": stats.get("nindexes", 0)
        }
    except HTTPException:
        raise
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{collection_name}", response_model=CollectionResponse)
async def delete_collection(
    collection_name: str,
    db = Depends(get_db)
):
    """Delete a collection from MongoDB"""
    try:
        # Check if collection exists
        existing_collections = await db.list_collection_names()
        if collection_name not in existing_collections:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        collection = db[collection_name]
        await collection.drop()
        
        return CollectionResponse(
            message="Collection deleted successfully",
            collection_name=collection_name
        )
    except HTTPException:
        raise
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))