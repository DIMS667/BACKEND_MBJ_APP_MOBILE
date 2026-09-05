from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base
from app.shared.models import TimestampMixin


class Child(Base, TimestampMixin):
    __tablename__ = "children"

    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    first_name = Column(String, nullable=False)
    level = Column(Integer, default=1, nullable=False)

    parent = relationship("User", back_populates="children")
    sensory_profile = relationship(
        "SensoryProfile",
        back_populates="child",
        uselist=False,
        cascade="all, delete-orphan",
    )
    preferences = relationship(
        "ChildPreferences",
        back_populates="child",
        uselist=False,
        cascade="all, delete-orphan",
    )


class SensoryProfile(Base, TimestampMixin):
    __tablename__ = "sensory_profiles"

    child_id = Column(Integer, ForeignKey("children.id", ondelete="CASCADE"), unique=True, nullable=False)
    noise_sensitive = Column(Boolean, default=False)
    light_sensitive = Column(Boolean, default=False)
    color_sensitive = Column(Boolean, default=False)
    motion_sensitive = Column(Boolean, default=False)
    transition_speed = Column(String, default="normal", nullable=False)

    child = relationship("Child", back_populates="sensory_profile")


class ChildPreferences(Base, TimestampMixin):
    __tablename__ = "child_preferences"

    child_id = Column(Integer, ForeignKey("children.id", ondelete="CASCADE"), unique=True, nullable=False)
    favorite_activities = Column(JSON, default=list)  # ex: ["jeux", "histoires"]
    color_theme = Column(String, default="blue")       # blue, green, lilac, yellow
    avatar_id = Column(String, nullable=True)

    child = relationship("Child", back_populates="preferences")