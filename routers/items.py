from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field

from config import get_database
from pymongo.errors import DuplicateKeyError, PyMongoError


def parse_dt(value: Optional[str]) -> Optional[datetime]:
    """
    Accepts:
      - "2026-01-01" (time optional -> defaults 00:00:00)
      - "2026-01-01 00:00:00"
      - "2026-01-01T00:00:00"
      - with timezone like "+05:30" or "Z"
    Returns an aware datetime (UTC).
    """
    if not value:
        return None

    s = value.strip()

    # allow space instead of 'T'
    s = s.replace(" ", "T")

    # if only date provided, add midnight
    if len(s) == 10:  # YYYY-MM-DD
        s = s + "T00:00:00"

    # allow trailing Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    dt = datetime.fromisoformat(s)

    # if no timezone provided, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


router = APIRouter(tags=["Documents"])

# IMPORTANT:
# If your event timestamp is nested inside a wrapper like { "data": { "event_timestamp": ... } }
# change this to: EVENT_TS_FIELD = "data.event_timestamp"
EVENT_TS_FIELD = "event_timestamp"


# ---------- Pydantic Schemas ----------

class DocumentCreate(BaseModel):
    data: Dict[str, Any] = Field(..., description="Document fields to insert")


class DocumentUpdate(BaseModel):
    data: Dict[str, Any] = Field(..., description="Fields to update (partial update)")


class DocumentsListResponse(BaseModel):
    documents: List[Dict[str, Any]]
    count: int  # count of documents returned in THIS response


# ---------- Helpers ----------

def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Mongo ObjectId -> str for JSON responses."""
    if "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    return doc


def _collection(collection_name: str):
    db = get_database()
    return db[collection_name]


def _parse_event_ts(value):
    """Parse incoming event_timestamp to timezone-aware UTC datetime for Mongo Date storage."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        s = value.strip().replace(" ", "T")
        if len(s) == 10:
            s += "T00:00:00"
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def _parse_company_ids(company_id_raw: Optional[str]) -> Optional[List[int]]:
    """
    Accepts:
      - None
      - "13"
      - "13,4,15"
      - " 13, 4 ,15 "
    Returns list[int] or None
    """
    if not company_id_raw:
        return None

    parts = [p.strip() for p in company_id_raw.split(",") if p.strip()]
    if not parts:
        return None

    ids: List[int] = []
    for p in parts:
        try:
            ids.append(int(p))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"company_id must be an integer or comma-separated integers. Invalid value: '{p}'"
            )
    return ids


# ---------- Routes ----------

@router.get(
    "/collections/{collection_name}/documents/",
    response_model=DocumentsListResponse,
    summary="List Documents",
    description="List all documents in the collection (optionally filtered by event_timestamp between start and end, and by company_id).",
)
async def list_documents(
    collection_name: str = Path(..., description="Name of the collection"),

    # limit OPTIONAL: if omitted, return ALL matches
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=1000,
        description="Optional. If provided, returns only this many records. If omitted, returns all matching records.",
    ),

    start: Optional[str] = Query(
        None,
        description="Start date/time. Examples: 2026-01-01 or 2026-01-01 00:00:00 or 2026-01-01T00:00:00Z",
        examples=["2026-01-01 00:00:00"],
    ),

    end: Optional[str] = Query(
        None,
        description="End date/time. Examples: 2026-01-10 or 2026-01-10 23:59:59 or 2026-01-10T23:59:59Z",
        examples=["2026-01-10 23:59:59"],
    ),

    # accept comma-separated company IDs using the SAME query name: company_id=13,4,15
    company_id: Optional[str] = Query(
        None,
        description="Optional. Comma-separated company IDs. Example: 13,4,15",
        examples=["13,4,15"],
    ),
):
    start_utc = parse_dt(start)
    end_utc = parse_dt(end)

    # If user passes end as DATE only (YYYY-MM-DD), treat it as end of that day (23:59:59)
    if end and len(end.strip()) == 10 and end_utc:
        end_utc = end_utc.replace(hour=23, minute=59, second=59)

    if start_utc and end_utc and start_utc > end_utc:
        raise HTTPException(status_code=400, detail="start must be <= end")

    company_ids = _parse_company_ids(company_id)

    col = _collection(collection_name)

    query: Dict[str, Any] = {}

    # Filter by event_timestamp range (optional)
    if start_utc or end_utc:
        query[EVENT_TS_FIELD] = {}
        if start_utc:
            query[EVENT_TS_FIELD]["$gte"] = start_utc
        if end_utc:
            query[EVENT_TS_FIELD]["$lte"] = end_utc

    # Filter by company_id(s) (optional)
    if company_ids:
        if len(company_ids) == 1:
            query["company_id"] = company_ids[0]
        else:
            query["company_id"] = {"$in": company_ids}

    cursor = col.find(query).sort(EVENT_TS_FIELD, -1)

    # Apply limit only if provided
    if limit is not None:
        cursor = cursor.limit(limit)
        docs = await cursor.to_list(length=limit)
    else:
        docs = await cursor.to_list(length=None)

    docs = [_serialize(d) for d in docs]

    # count = how many records returned in this response
    return DocumentsListResponse(documents=docs, count=len(docs))


@router.post("/collections/{collection_name}/documents/")
async def create_document(collection_name: str, document: DocumentCreate):
    col = _collection(collection_name)
    payload = dict(document.data)

    # convert string -> datetime (Mongo Date)
    if "event_timestamp" in payload:
        payload["event_timestamp"] = _parse_event_ts(payload["event_timestamp"])
    else:
        payload["event_timestamp"] = datetime.now(timezone.utc)

    try:
        result = await col.insert_one(payload)
    except DuplicateKeyError as e:
        raise HTTPException(status_code=409, detail=f"Duplicate key: {str(e)}")
    except PyMongoError as e:
        # show real mongo error (helps debugging instead of plain 500)
        raise HTTPException(status_code=500, detail=f"Mongo error: {str(e)}")

    created = await col.find_one({"_id": result.inserted_id})
    return _serialize(created)



@router.get(
    "/collections/{collection_name}/documents/{document_id}",
    summary="Get Document",
)
async def get_document(collection_name: str, document_id: str):
    col = _collection(collection_name)

    try:
        oid = ObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document_id")

    doc = await col.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return _serialize(doc)


@router.put(
    "/collections/{collection_name}/documents/{document_id}",
    summary="Update Document",
)
async def update_document(collection_name: str, document_id: str, document: DocumentUpdate):
    col = _collection(collection_name)

    try:
        oid = ObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document_id")

    existing = await col.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found")

    update_data = dict(document.data)
    update_data.pop("_id", None)

    result = await col.update_one({"_id": oid}, {"$set": update_data})
    updated = await col.find_one({"_id": oid})

    return {
        "matched": result.matched_count,
        "modified": result.modified_count,
        "document": _serialize(updated),
    }


@router.delete(
    "/collections/{collection_name}/documents/{document_id}",
    summary="Delete Document",
)
async def delete_document(collection_name: str, document_id: str):
    col = _collection(collection_name)

    try:
        oid = ObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document_id")

    result = await col.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")

    return {"deleted": True, "document_id": document_id}
