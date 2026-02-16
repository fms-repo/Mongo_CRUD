from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from routers import admin, items
from config import get_mongodb_client, close_mongodb_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize MongoDB connection    
    get_mongodb_client()
    yield
    # Shutdown: Close MongoDB connection
    await close_mongodb_connection()


app = FastAPI(
    title="MongoDB CRUD API",
    description="FastAPI application for MongoDB collection and document management",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(admin.router)
app.include_router(items.router)

@app.get("/")
async def root():
    return {
        "message": "MongoDB CRUD API",
        "docs": "/docs",
        "endpoints": {
            "collection_management": "/admin/collections",
            "document_operations": "/collections/{collection_name}/documents"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)