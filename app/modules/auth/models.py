from sqlalchemy import Column, String, Boolean, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.database import Base
from app.shared.models import TimestampMixin
import enum


class UserRole(str, enum.Enum):
    PARENT = "parent"
    EDUCATOR = "educator"
    ADMIN = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.PARENT, nullable=False)
    photo_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    children = relationship(
        "Child", back_populates="parent", cascade="all, delete-orphan"
    )


class RefreshToken(Base, TimestampMixin):
    __tablename__ = "refresh_tokens"

    token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_revoked = Column(Boolean, default=False)

    user = relationship("User", back_populates="refresh_tokens")