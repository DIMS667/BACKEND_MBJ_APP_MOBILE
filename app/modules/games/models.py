from sqlalchemy import Column, String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.shared.models import TimestampMixin


class GameCategory(Base, TimestampMixin):
    __tablename__ = "game_categories"

    name = Column(String, nullable=False, unique=True)
    # memory / concentration / logic / recognition / association
    description = Column(String, nullable=True)
    icon_url = Column(String, nullable=True)
    color = Column(String, nullable=False, default="#4A90D9")
    order = Column(Integer, default=0)

    games = relationship(
        "Game",
        back_populates="category",
        cascade="all, delete-orphan",
    )


class Game(Base, TimestampMixin):
    __tablename__ = "games"

    category_id = Column(
        Integer,
        ForeignKey("game_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    icon_url = Column(String, nullable=True)
    min_level = Column(Integer, default=1)
    max_level = Column(Integer, default=5)
    is_offline_available = Column(Boolean, default=True)  # CDC : offline obligatoire

    category = relationship("GameCategory", back_populates="games")
    scores = relationship(
        "GameScore",
        back_populates="game",
        cascade="all, delete-orphan",
    )
    progress = relationship(
        "GameProgress",
        back_populates="game",
        cascade="all, delete-orphan",
    )


class GameScore(Base, TimestampMixin):
    __tablename__ = "game_scores"

    game_id = Column(
        Integer,
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    child_id = Column(
        Integer,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
    )
    score = Column(Integer, nullable=False, default=0)
    level = Column(Integer, nullable=False, default=1)
    duration_seconds = Column(Integer, nullable=True)  # durée de la partie

    game = relationship("Game", back_populates="scores")


class GameProgress(Base, TimestampMixin):
    __tablename__ = "game_progress"

    game_id = Column(
        Integer,
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    child_id = Column(
        Integer,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
    )
    current_level = Column(Integer, default=1)
    best_score = Column(Integer, default=0)
    total_plays = Column(Integer, default=0)

    # Seuil pour passer au niveau suivant (CDC : adaptation invisible)
    # L'enfant doit réussir 3 fois de suite avant de monter de niveau
    consecutive_successes = Column(Integer, default=0)

    game = relationship("Game", back_populates="progress")