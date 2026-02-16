from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

# Collection Management Models
class CreateCollectionRequest(BaseModel):
    collection_name: str = Field(..., description="Name of the collection to create")

class CollectionResponse(BaseModel):
    message: str
    collection_name: str
    status: Optional[str] = None

# Document CRUD Models
class DocumentCreate(BaseModel):
    data: Dict[str, Any] = Field(..., description="Document data as key-value pairs")

class DocumentUpdate(BaseModel):
    data: Dict[str, Any] = Field(..., description="Updated document data")

class DocumentResponse(BaseModel):
    document: Dict[str, Any]

class DocumentsListResponse(BaseModel):
    documents: List[Dict[str, Any]]
    count: int