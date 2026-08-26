import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from app.database import Base
from app.shared.models import TimestampMixin


class Emotion(Base, TimestampMixin):
    __tablename__ = "emotions"

    name = Column(String, nullable=False, unique=True)  # joie, tristesse...
    icon_url = Column(String, nullable=True)
    color = Column(String, nullable=False, default="#4A90D9")
    is_positive = Column(Boolean, default=True)  # pour proposer activités apaisantes

    records = relationship(
        "EmotionRecord",
        back_populates="emotion",
        cascade="all, delete-orphan"
    )


class EmotionRecord(Base, TimestampMixin):
    __tablename__ = "emotion_records"
    __table_args__ = (
        UniqueConstraint(
            "child_id",
            "client_uuid",
            name="uq_emotion_records_child_client",
        ),
        CheckConstraint(
            "intensity IS NULL OR intensity IN ('doux', 'moyen', 'fort')",
            name="ck_emotion_records_intensity",
        ),
        Index(
            "ix_emotion_records_child_recorded_at",
            "child_id",
            "recorded_at",
        ),
    )

    child_id = Column(Integer, ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    emotion_id = Column(Integer, ForeignKey("emotions.id", ondelete="CASCADE"), nullable=False)
    client_uuid = Column(
        String(64),
        nullable=False,
        default=lambda: uuid.uuid4().hex,
    )
    context = Column(String, nullable=True)  # contexte optionnel (matin, école...)

    context_key = Column(String(32), nullable=True)
    intensity = Column(String(16), nullable=True)
    recorded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    emotion = relationship("Emotion", back_populates="records")
    calming_feedback = relationship(
        "CalmingActivityFeedback",
        back_populates="emotion_record",
        cascade="all, delete-orphan",
    )


class CalmingActivity(Base, TimestampMixin):
    __tablename__ = "calming_activities"

    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # breathing, music, animation, game
    description = Column(String, nullable=True)
    content_url = Column(String, nullable=True)
    duration_seconds = Column(Integer, default=60)
    icon_url = Column(String, nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

    feedback = relationship(
        "CalmingActivityFeedback",
        back_populates="activity",
    )


class CalmingActivityFeedback(Base, TimestampMixin):
    __tablename__ = "calming_activity_feedback"
    __table_args__ = (
        UniqueConstraint(
            "child_id",
            "client_uuid",
            name="uq_calming_feedback_child_client",
        ),
        Index(
            "ix_calming_feedback_child_activity_recorded",
            "child_id",
            "activity_id",
            "recorded_at",
        ),
    )

    child_id = Column(
        Integer,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
    )
    emotion_record_id = Column(
        Integer,
        ForeignKey("emotion_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_id = Column(
        Integer,
        ForeignKey("calming_activities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    client_uuid = Column(String(64), nullable=False)
    helped = Column(Boolean, nullable=False)
    recorded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    emotion_record = relationship(
        "EmotionRecord",
        back_populates="calming_feedback",
    )
    activity = relationship(
        "CalmingActivity",
        back_populates="feedback",
    )
