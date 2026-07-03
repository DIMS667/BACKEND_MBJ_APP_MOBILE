from sqlalchemy import Column, String, Integer, ForeignKey, Boolean
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

    child_id = Column(Integer, ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    emotion_id = Column(Integer, ForeignKey("emotions.id", ondelete="CASCADE"), nullable=False)
    context = Column(String, nullable=True)  # contexte optionnel (matin, école...)

    emotion = relationship("Emotion", back_populates="records")


class CalmingActivity(Base, TimestampMixin):
    __tablename__ = "calming_activities"

    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # breathing, music, animation, game
    description = Column(String, nullable=True)
    content_url = Column(String, nullable=True)
    duration_seconds = Column(Integer, default=60)
    icon_url = Column(String, nullable=True)