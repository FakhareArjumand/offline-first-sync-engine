from sqlalchemy import Column, String, DateTime, JSON
from .database import Base
from datetime import datetime

class ServerSyncRecord(Base):
    __tablename__ = "sync_records"

    id = Column(String, primary_key=True, index=True)
    table_name = Column(String, index=True)
    payload = Column(JSON)  # Stores the actual row data (e.g., user name, email, etc.)
    updated_at = Column(DateTime, default=datetime.utcnow)