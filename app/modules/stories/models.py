from sqlalchemy import Column, String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.shared.models import TimestampMixin


class Story(Base, TimestampMixin):
    __tablename__ = "stories"

    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    cover_url = Column(String, nullable=True)
    category = Column(String, nullable=False)
    # greeting/turn/sharing/doctor/school/help/anger
    difficulty_level = Column(Integer, default=1)  # 1=facile, 2=moyen, 3=difficile
    is_offline_available = Column(Boolean, default=True)
    total_pages = Column(Integer, default=0)

    pages = relationship(
        "StoryPage",
        back_populates="story",
        cascade="all, delete-orphan",
        order_by="StoryPage.page_number",
    )
    progress = relationship(
        "StoryProgress",
        back_populates="story",
        cascade="all, delete-orphan",
    )


class StoryPage(Base, TimestampMixin):
    __tablename__ = "story_pages"

    story_id = Column(
        Integer,
        ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_number = Column(Integer, nullable=False)
    text = Column(String, nullable=False)       # texte court (< 10 mots)
    image_url = Column(String, nullable=True)   # illustration ARASAAC
    audio_url = Column(String, nullable=True)   # narration gTTS
    animation_type = Column(String, nullable=True)  # fade/slide/none

    story = relationship("Story", back_populates="pages")


class StoryProgress(Base, TimestampMixin):
    __tablename__ = "story_progress"

    story_id = Column(
        Integer,
        ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False,
    )
    child_id = Column(
        Integer,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
    )
    last_page = Column(Integer, default=1)
    is_completed = Column(Boolean, default=False)
    read_count = Column(Integer, default=0)  # nombre de fois lue

    story = relationship("Story", back_populates="progress")