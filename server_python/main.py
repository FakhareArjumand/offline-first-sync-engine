from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

# Database imports
from app.db.database import engine, Base, get_db
from app.db import models
from app.db.models import ServerSyncRecord

# Generate the database tables automatically when the server starts
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Arjumand Labs | Sync Engine",
    description="Bidirectional sync resolver for offline-first clients.",
    version="1.0.0"
)

# --- Pydantic Models for the Sync Payload ---
class SyncRecord(BaseModel):
    id: str
    table_name: str
    action: str  # INSERT, UPDATE, DELETE
    payload: dict
    updated_at: datetime

class SyncRequest(BaseModel):
    client_id: str
    last_sync_timestamp: datetime
    mutations: List[SyncRecord]

class SyncResponse(BaseModel):
    status: str
    resolved_conflicts: int
    server_mutations: List[SyncRecord]


# --- Core Sync Endpoint ---
@app.post("/api/sync", response_model=SyncResponse)
async def process_sync(request: SyncRequest, db: Session = Depends(get_db)):
    """
    The Core Conflict Resolution Engine.
    Compares client mutations against the server database using UTC timestamps.
    """
    server_mutations_to_return = []
    resolved_conflicts_count = 0

    # 1. Process incoming client mutations
    for client_record in request.mutations:
        # Check if the record already exists on the server
        server_record = db.query(ServerSyncRecord).filter(ServerSyncRecord.id == client_record.id).first()

        if not server_record:
            # Record doesn't exist on server -> Insert it
            new_record = ServerSyncRecord(
                id=client_record.id,
                table_name=client_record.table_name,
                payload=client_record.payload,
                updated_at=client_record.updated_at
            )
            db.add(new_record)
        else:
            # Conflict detected! Compare timestamps.
            # If client is newer, overwrite server.
            # NOTE: We make timestamps naive to compare them safely
            if client_record.updated_at.replace(tzinfo=None) > server_record.updated_at.replace(tzinfo=None):
                server_record.payload = client_record.payload
                server_record.updated_at = client_record.updated_at.replace(tzinfo=None)
                resolved_conflicts_count += 1
            # If server is newer, server wins.

    db.commit()

    # 2. Fetch server updates that the client missed while offline
    missed_updates = db.query(ServerSyncRecord).filter(
        ServerSyncRecord.updated_at > request.last_sync_timestamp.replace(tzinfo=None)
    ).all()

    for update in missed_updates:
        server_mutations_to_return.append(SyncRecord(
            id=update.id,
            table_name=update.table_name,
            action="UPSERT",
            payload=update.payload,
            updated_at=update.updated_at
        ))

    return SyncResponse(
        status="success",
        resolved_conflicts=resolved_conflicts_count,
        server_mutations=server_mutations_to_return
    )


# --- Health Check ---
@app.get("/")
def health_check():
    return {"status": "online", "engine": "running"}