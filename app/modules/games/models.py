from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Index, UniqueConstraint
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
        index=True,
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
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "child_id",
            "session_id",
            name="uq_game_scores_session",
        ),
        Index("ix_game_scores_child_created", "child_id", "created_at"),
    )

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
    session_id = Column(String(64), nullable=True)
    correct_answers = Column(Integer, nullable=False, default=0)
    total_questions = Column(Integer, nullable=False, default=0)
    mistake_count = Column(Integer, nullable=False, default=0)
    hints_used = Column(Integer, nullable=False, default=0)
    completed = Column(Boolean, nullable=False, default=True)
    independent_success = Column(Boolean, nullable=False, default=False)
    evidence_score = Column(Integer, nullable=False, default=0)

    game = relationship("Game", back_populates="scores")


class GameProgress(Base, TimestampMixin):
    __tablename__ = "game_progress"
    __table_args__ = (
        # Aussi l'index qui sert le lookup (child_id, game_id) fait par
        # submit_score()/get_child_progress() — un enfant a au plus une
        # ligne de progression par jeu, la contrainte l'impose en DB.
        UniqueConstraint(
            "child_id",
            "game_id",
            name="uq_game_progress_child_game",
        ),
    )

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
    mastery_percent = Column(Integer, nullable=False, default=0)
    independent_streak = Column(Integer, nullable=False, default=0)
    struggle_streak = Column(Integer, nullable=False, default=0)
    is_mastered = Column(Boolean, nullable=False, default=False)

    game = relationship("Game", back_populates="progress")
