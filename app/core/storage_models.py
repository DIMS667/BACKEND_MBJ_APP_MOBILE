"""Persisted filesystem cleanup jobs (separate from deletable user rows)."""

from sqlalchemy import Column, DateTime, Integer, String, func

from app.database import Base


class PendingFileDeletion(Base):
    __tablename__ = "pending_file_deletions"

    id = Column(Integer, primary_key=True)
    file_path = Column(String, nullable=False)
    owner_directory = Column(String, nullable=False)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
