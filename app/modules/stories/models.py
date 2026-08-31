from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
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
    is_offline_available = Column(Boolean, default=True)
    total_pages = Column(Integer, default=0)
    is_custom = Column(Boolean, default=False, nullable=False)
    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    child_id = Column(
        Integer,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    client_uuid = Column(String(64), nullable=True, unique=True, index=True)

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
    favorites = relationship(
        "StoryFavorite",
        back_populates="story",
        cascade="all, delete-orphan",
    )


class StoryPage(Base, TimestampMixin):
    __tablename__ = "story_pages"

    story_id = Column(
        Integer,
        ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number = Column(Integer, nullable=False)
    text = Column(String, nullable=False)       # texte court (< 10 mots)
    image_url = Column(String, nullable=True)   # illustration ARASAAC
    audio_url = Column(String, nullable=True)   # narration gTTS
    animation_type = Column(String, nullable=True)  # fade/slide/none
    pictogram_url = Column(String, nullable=True)
    local_page_key = Column(String(64), nullable=True)
    next_page_number = Column(Integer, nullable=True)

    story = relationship("Story", back_populates="pages")
    choices = relationship(
        "StoryChoice",
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="StoryChoice.sort_order",
    )


class StoryChoice(Base, TimestampMixin):
    __tablename__ = "story_choices"

    page_id = Column(
        Integer,
        ForeignKey("story_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label = Column(String(120), nullable=False)
    pictogram_url = Column(String, nullable=True)
    next_page_number = Column(Integer, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    page = relationship("StoryPage", back_populates="choices")


class StoryProgress(Base, TimestampMixin):
    __tablename__ = "story_progress"
    __table_args__ = (
        # child_id en tête : les lectures filtrent par enfant seul
        # (dashboard, liste de progression) bien plus souvent que par histoire seule.
        UniqueConstraint("child_id", "story_id", name="uq_story_progress_child_story"),
    )

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
    selected_choices = Column(JSON, default=dict, nullable=False)

    story = relationship("Story", back_populates="progress")


class StoryFavorite(Base, TimestampMixin):
    __tablename__ = "story_favorites"
    __table_args__ = (
        UniqueConstraint("child_id", "story_id", name="uq_story_favorite_child_story"),
    )

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

    story = relationship("Story", back_populates="favorites")


class StoryMedia(Base, TimestampMixin):
    __tablename__ = "story_media"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_uuid",
            name="uq_story_media_owner_client",
        ),
    )

    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_uuid = Column(String(64), nullable=False)
    file_path = Column(String, nullable=False)
    content_type = Column(String(40), nullable=False)
    original_name = Column(String(255), nullable=True)
