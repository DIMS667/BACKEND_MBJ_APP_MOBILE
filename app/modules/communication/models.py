from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base
from app.shared.models import TimestampMixin


class PictoCategory(Base, TimestampMixin):
    __tablename__ = "picto_categories"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_uuid",
            name="uq_picto_categories_owner_client",
        ),
    )

    name = Column(String, nullable=False)
    icon_url = Column(String, nullable=True)
    color = Column(String, nullable=False, default="#4A90D9")
    order = Column(Integer, default=0)
    is_default = Column(Boolean, default=True, nullable=False)
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
    client_uuid = Column(String(64), nullable=True, index=True)

    pictograms = relationship(
        "Pictogram",
        back_populates="category",
        cascade="all, delete-orphan"
    )


class Pictogram(Base, TimestampMixin):
    __tablename__ = "pictograms"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_uuid",
            name="uq_pictograms_owner_client",
        ),
    )

    category_id = Column(Integer, ForeignKey("picto_categories.id", ondelete="CASCADE"), nullable=False)
    label = Column(String, nullable=False)
    image_url = Column(String, nullable=False)
    audio_url = Column(String, nullable=True)
    is_default = Column(Boolean, default=True, nullable=False)
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
    client_uuid = Column(String(64), nullable=True, index=True)

    category = relationship("PictoCategory", back_populates="pictograms")
    favorites = relationship(
        "FavoritePicto",
        back_populates="pictogram",
        cascade="all, delete-orphan"
    )


class FavoritePicto(Base, TimestampMixin):
    __tablename__ = "favorite_pictos"

    child_id = Column(Integer, ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    picto_id = Column(Integer, ForeignKey("pictograms.id", ondelete="CASCADE"), nullable=False)

    pictogram = relationship("Pictogram", back_populates="favorites")


class SentenceHistory(Base, TimestampMixin):
    __tablename__ = "sentence_histories"

    child_id = Column(Integer, ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    sentence_pictos = Column(JSON, default=list)  # liste des ids pictos
    sentence_text = Column(String, nullable=False)  # ex: "Je veux boire"
    audio_url = Column(String, nullable=True)       # fichier audio généré


class PictogramMedia(Base, TimestampMixin):
    __tablename__ = "pictogram_media"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "client_uuid",
            name="uq_pictogram_media_owner_client",
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
