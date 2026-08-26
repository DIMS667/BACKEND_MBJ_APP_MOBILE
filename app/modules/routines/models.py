from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base
from app.shared.models import TimestampMixin


class Routine(Base, TimestampMixin):
    __tablename__ = "routines"

    child_id = Column(Integer, ForeignKey("children.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    icon_url = Column(String, nullable=True)
    type = Column(String, nullable=False, default="custom")  # morning/evening/school/custom
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, nullable=False, default=False)

    steps = relationship(
        "RoutineStep",
        back_populates="routine",
        cascade="all, delete-orphan",
        order_by="RoutineStep.order",
    )
    sessions = relationship(
        "RoutineSession",
        back_populates="routine",
        cascade="all, delete-orphan",
    )


class RoutineStep(Base, TimestampMixin):
    __tablename__ = "routine_steps"
    __table_args__ = (
        UniqueConstraint(
            "routine_id",
            "client_uuid",
            name="uq_routine_steps_routine_client",
        ),
        UniqueConstraint(
            "routine_id",
            "order",
            name="uq_routine_steps_routine_order",
        ),
        CheckConstraint("\"order\" >= 1", name="ck_routine_steps_order_positive"),
    )

    routine_id = Column(Integer, ForeignKey("routines.id", ondelete="CASCADE"), nullable=False)
    order = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    audio_url = Column(String, nullable=True)
    is_completed = Column(Boolean, default=False)
    is_default = Column(Boolean, nullable=False, default=False)
    client_uuid = Column(String(64), nullable=True, index=True)

    routine = relationship("Routine", back_populates="steps")


class RoutineSession(Base, TimestampMixin):
    __tablename__ = "routine_sessions"

    routine_id = Column(Integer, ForeignKey("routines.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(String, nullable=True)
    completed_at = Column(String, nullable=True)
    steps_completed = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)

    routine = relationship("Routine", back_populates="sessions")
