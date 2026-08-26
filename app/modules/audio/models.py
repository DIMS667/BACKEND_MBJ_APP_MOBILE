from sqlalchemy import Column, String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.shared.models import TimestampMixin


class AudioCategory(Base, TimestampMixin):
    __tablename__ = "audio_categories"

    name = Column(String, nullable=False, unique=True)
    # narration / calming / feedback / tts
    description = Column(String, nullable=True)
    icon_url = Column(String, nullable=True)

    files = relationship(
        "AudioFile",
        back_populates="category",
        cascade="all, delete-orphan",
    )


class AudioFile(Base, TimestampMixin):
    __tablename__ = "audio_files"

    category_id = Column(
        Integer,
        ForeignKey("audio_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    language = Column(String, default="fr")
    is_local = Column(Boolean, default=True)  # fichier local ou URL distante

    category = relationship("AudioCategory", back_populates="files")