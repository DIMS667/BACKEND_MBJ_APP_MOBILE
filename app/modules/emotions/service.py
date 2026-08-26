import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cache import cached
from app.modules.children.models import Child

from .models import (
    CalmingActivity,
    CalmingActivityFeedback,
    Emotion,
    EmotionRecord,
)
from .schemas import CalmingFeedbackSync, EmotionRecordCreate, EmotionRecordSync


MIN_PERSONALIZATION_FEEDBACK = 2

LEGACY_CONTEXT_KEYS = {
    "maison": "maison",
    "école": "ecole",
    "ecole": "ecole",
    "repas": "repas",
    "transport": "transport",
    "bruit": "bruit",
    "soin": "soin",
    "jeu": "jeu",
    "changement": "changement",
    "attente": "attente",
    "avec_autres": "avec_autres",
    "seul": "seul",
    "autre": "autre",
}


def parse_legacy_context(value: str | None) -> tuple[str | None, str | None]:
    """Extract structured values without destroying the legacy context."""
    context_key: str | None = None
    intensity: str | None = None
    if not value:
        return context_key, intensity

    for raw_part in value.split("|"):
        part = raw_part.strip().lower()
        normalized_part = part.replace("intensité:", "intensite:")
        if normalized_part.startswith("intensite:"):
            raw_intensity = normalized_part.split(":", 1)[1].strip()
            if raw_intensity in {"doux", "faible"}:
                intensity = "doux"
            elif raw_intensity in {"moyen", "fort"}:
                intensity = raw_intensity
        elif context_key is None and part in LEGACY_CONTEXT_KEYS:
            context_key = LEGACY_CONTEXT_KEYS[part]

    return context_key, intensity


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _same_instant(left: datetime, right: datetime) -> bool:
    return _as_utc(left) == _as_utc(right)


async def _check_child_ownership(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
) -> Child:
    result = await db.execute(select(Child).where(Child.id == child_id))
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enfant introuvable.",
        )
    if child.parent_id != parent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé.",
        )
    return child


async def _get_record_by_client_uuid(
    db: AsyncSession,
    child_id: int,
    client_uuid: str,
) -> EmotionRecord | None:
    result = await db.execute(
        select(EmotionRecord)
        .options(selectinload(EmotionRecord.emotion))
        .where(
            EmotionRecord.child_id == child_id,
            EmotionRecord.client_uuid == client_uuid,
        )
    )
    return result.scalar_one_or_none()


async def _get_record_by_id(
    db: AsyncSession,
    record_id: int,
) -> EmotionRecord:
    result = await db.execute(
        select(EmotionRecord)
        .options(selectinload(EmotionRecord.emotion))
        .where(EmotionRecord.id == record_id)
    )
    return result.scalar_one()


def _emotion_record_matches(
    record: EmotionRecord,
    *,
    emotion_id: int,
    context: str | None,
    context_key: str | None,
    intensity: str | None,
    recorded_at: datetime,
    compare_recorded_at: bool = True,
) -> bool:
    return (
        record.emotion_id == emotion_id
        and record.context == context
        and record.context_key == context_key
        and record.intensity == intensity
        and (
            not compare_recorded_at
            or _same_instant(record.recorded_at, recorded_at)
        )
    )


async def get_all_emotions(db: AsyncSession) -> list[Emotion]:
    async def _load():
        result = await db.execute(select(Emotion).order_by(Emotion.id))
        return list(result.scalars().all())
    return await cached("emotions:all", _load)


async def _save_emotion(
    db: AsyncSession,
    data: EmotionRecordCreate | EmotionRecordSync,
    parent_id: int,
) -> EmotionRecord:
    from app.websocket.manager import manager

    await _check_child_ownership(db, data.child_id, parent_id)

    legacy_context_key, legacy_intensity = parse_legacy_context(data.context)
    context_key = data.context_key or legacy_context_key
    intensity = data.intensity or legacy_intensity
    recorded_at = _as_utc(data.recorded_at or datetime.now(timezone.utc))
    client_uuid = data.client_uuid or uuid.uuid4().hex

    existing = await _get_record_by_client_uuid(
        db,
        data.child_id,
        client_uuid,
    )
    if existing is not None:
        if not _emotion_record_matches(
            existing,
            emotion_id=data.emotion_id,
            context=data.context,
            context_key=context_key,
            intensity=intensity,
            recorded_at=recorded_at,
            compare_recorded_at=data.recorded_at is not None,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet identifiant client désigne un autre enregistrement.",
            )
        return existing

    result = await db.execute(
        select(Emotion).where(Emotion.id == data.emotion_id)
    )
    emotion = result.scalar_one_or_none()
    if not emotion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Émotion introuvable.",
        )

    record = EmotionRecord(
        child_id=data.child_id,
        emotion_id=data.emotion_id,
        client_uuid=client_uuid,
        context=data.context,
        context_key=context_key,
        intensity=intensity,
        recorded_at=recorded_at,
    )
    db.add(record)
    try:
        await db.flush()
    except IntegrityError as exc:
        # A concurrent replay may pass the initial SELECT. The database
        # constraint remains the source of truth.
        await db.rollback()
        existing = await _get_record_by_client_uuid(
            db,
            data.child_id,
            client_uuid,
        )
        if existing is None:
            raise exc
        if not _emotion_record_matches(
            existing,
            emotion_id=data.emotion_id,
            context=data.context,
            context_key=context_key,
            intensity=intensity,
            recorded_at=recorded_at,
            compare_recorded_at=data.recorded_at is not None,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet identifiant client désigne un autre enregistrement.",
            ) from exc
        return existing

    stored_record = await _get_record_by_id(db, record.id)

    await manager.send_to_child(
        data.child_id,
        {
            "type": "emotion_recorded",
            "data": {
                "child_id": data.child_id,
                "client_uuid": client_uuid,
                "emotion_name": emotion.name,
                "emotion_color": emotion.color,
                "is_positive": emotion.is_positive,
                "context": data.context,
                "context_key": context_key,
                "intensity": intensity,
                "recorded_at": recorded_at.isoformat(),
            },
        },
    )
    return stored_record


async def save_emotion(
    db: AsyncSession,
    data: EmotionRecordCreate,
    parent_id: int,
) -> EmotionRecord:
    return await _save_emotion(db, data, parent_id)


async def sync_emotion(
    db: AsyncSession,
    data: EmotionRecordSync,
    parent_id: int,
) -> EmotionRecord:
    return await _save_emotion(db, data, parent_id)


async def get_emotion_history(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
    limit: int = 30,
) -> list[EmotionRecord]:
    await _check_child_ownership(db, child_id, parent_id)

    result = await db.execute(
        select(EmotionRecord)
        .options(selectinload(EmotionRecord.emotion))
        .where(EmotionRecord.child_id == child_id)
        .order_by(
            EmotionRecord.recorded_at.desc(),
            EmotionRecord.id.desc(),
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_emotion_stats(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
    days: int = 30,
) -> dict[str, Any]:
    await _check_child_ownership(db, child_id, parent_id)

    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            Emotion.name,
            Emotion.color,
            func.count(EmotionRecord.id).label("count"),
        )
        .join(EmotionRecord, EmotionRecord.emotion_id == Emotion.id)
        .where(
            EmotionRecord.child_id == child_id,
            EmotionRecord.recorded_at >= since,
        )
        .group_by(Emotion.id, Emotion.name, Emotion.color)
        .order_by(func.count(EmotionRecord.id).desc(), Emotion.id)
    )
    rows = result.all()

    total = sum(row.count for row in rows)
    stats = [
        {
            "emotion_name": row.name,
            "color": row.color,
            "count": row.count,
            "percentage": round((row.count / total * 100), 1) if total else 0,
        }
        for row in rows
    ]
    return {
        "child_id": child_id,
        "total_records": total,
        "period_days": days,
        "stats": stats,
        "most_frequent": stats[0]["emotion_name"] if stats else None,
    }


def _stat_value(stats: Any, key: str, default: Any) -> Any:
    if stats is None:
        return default
    if isinstance(stats, Mapping):
        return stats.get(key, default)
    return getattr(stats, key, default)


def rank_calming_activities(
    activities: list[CalmingActivity],
    feedback_by_activity: Mapping[int, Any],
) -> list[dict[str, Any]]:
    """Return every activity, applying personalization only with evidence."""
    payloads: list[dict[str, Any]] = []
    for activity in activities:
        activity_stats = feedback_by_activity.get(activity.id)
        feedback_count = int(
            _stat_value(activity_stats, "feedback_count", 0) or 0
        )
        helped_count = int(
            _stat_value(activity_stats, "helped_count", 0) or 0
        )
        has_evidence = (
            feedback_count >= MIN_PERSONALIZATION_FEEDBACK
            and helped_count >= 1
        )
        score = (helped_count + 1) / (feedback_count + 2)
        payloads.append(
            {
                "id": activity.id,
                "name": activity.name,
                "type": activity.type,
                "description": activity.description,
                "content_url": activity.content_url,
                "duration_seconds": activity.duration_seconds,
                "icon_url": activity.icon_url,
                "display_order": activity.display_order,
                "is_active": activity.is_active,
                "feedback_count": feedback_count,
                "helped_count": helped_count,
                "last_helped_at": _stat_value(
                    activity_stats,
                    "last_helped_at",
                    None,
                ),
                "personalization_score": round(score, 6),
                "personalized": has_evidence,
            }
        )

    return sorted(
        payloads,
        key=lambda item: (
            -item["personalization_score"],
            item["display_order"],
            item["id"],
        ),
    )


async def _active_calming_activities(
    db: AsyncSession,
    activity_type: str | None = None,
) -> list[CalmingActivity]:
    async def _load():
        query = select(CalmingActivity).where(
            CalmingActivity.is_active.is_(True)
        )
        if activity_type:
            query = query.where(CalmingActivity.type == activity_type)
        result = await db.execute(
            query.order_by(
                CalmingActivity.display_order,
                CalmingActivity.id,
            )
        )
        return list(result.scalars().all())
    return await cached(f"emotions:calming:{activity_type or 'all'}", _load)


async def get_calming_activities(
    db: AsyncSession,
    activity_type: str | None = None,
) -> list[dict[str, Any]]:
    activities = await _active_calming_activities(db, activity_type)
    return rank_calming_activities(activities, {})


async def get_personalized_calming_activities(
    db: AsyncSession,
    child_id: int,
    parent_id: int,
    activity_type: str | None = None,
) -> list[dict[str, Any]]:
    await _check_child_ownership(db, child_id, parent_id)
    activities = await _active_calming_activities(db, activity_type)

    helped_value = case(
        (CalmingActivityFeedback.helped.is_(True), 1),
        else_=0,
    )
    last_helped_value = case(
        (
            CalmingActivityFeedback.helped.is_(True),
            CalmingActivityFeedback.recorded_at,
        ),
        else_=None,
    )
    result = await db.execute(
        select(
            CalmingActivityFeedback.activity_id,
            func.count(CalmingActivityFeedback.id).label("feedback_count"),
            func.sum(helped_value).label("helped_count"),
            func.max(last_helped_value).label("last_helped_at"),
        )
        .where(CalmingActivityFeedback.child_id == child_id)
        .group_by(CalmingActivityFeedback.activity_id)
    )
    feedback_by_activity = {
        row.activity_id: row
        for row in result.all()
    }
    return rank_calming_activities(activities, feedback_by_activity)


async def _get_feedback_by_client_uuid(
    db: AsyncSession,
    child_id: int,
    client_uuid: str,
) -> CalmingActivityFeedback | None:
    result = await db.execute(
        select(CalmingActivityFeedback).where(
            CalmingActivityFeedback.child_id == child_id,
            CalmingActivityFeedback.client_uuid == client_uuid,
        )
    )
    return result.scalar_one_or_none()


def _feedback_matches(
    feedback: CalmingActivityFeedback,
    *,
    emotion_record_id: int,
    activity_id: int,
    helped: bool,
    recorded_at: datetime,
) -> bool:
    return (
        feedback.emotion_record_id == emotion_record_id
        and feedback.activity_id == activity_id
        and feedback.helped is helped
        and _same_instant(feedback.recorded_at, recorded_at)
    )


def _feedback_payload(
    feedback: CalmingActivityFeedback,
    record_client_uuid: str,
) -> dict[str, Any]:
    return {
        "id": feedback.id,
        "client_uuid": feedback.client_uuid,
        "child_id": feedback.child_id,
        "emotion_record_id": feedback.emotion_record_id,
        "record_client_uuid": record_client_uuid,
        "activity_id": feedback.activity_id,
        "helped": feedback.helped,
        "recorded_at": feedback.recorded_at,
        "created_at": feedback.created_at,
    }


async def sync_calming_feedback(
    db: AsyncSession,
    data: CalmingFeedbackSync,
    parent_id: int,
) -> dict[str, Any]:
    await _check_child_ownership(db, data.child_id, parent_id)

    emotion_record = await _get_record_by_client_uuid(
        db,
        data.child_id,
        data.record_client_uuid,
    )
    if emotion_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enregistrement émotionnel introuvable.",
        )
    emotion_record_id = emotion_record.id

    existing = await _get_feedback_by_client_uuid(
        db,
        data.child_id,
        data.client_uuid,
    )
    recorded_at = _as_utc(data.recorded_at)
    if existing is not None:
        if not _feedback_matches(
            existing,
            emotion_record_id=emotion_record_id,
            activity_id=data.activity_id,
            helped=data.helped,
            recorded_at=recorded_at,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet identifiant client désigne un autre retour.",
            )
        return _feedback_payload(existing, data.record_client_uuid)

    activity_result = await db.execute(
        select(CalmingActivity).where(
            CalmingActivity.id == data.activity_id
        )
    )
    if activity_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activité apaisante introuvable.",
        )

    feedback = CalmingActivityFeedback(
        child_id=data.child_id,
        emotion_record_id=emotion_record_id,
        activity_id=data.activity_id,
        client_uuid=data.client_uuid,
        helped=data.helped,
        recorded_at=recorded_at,
    )
    db.add(feedback)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        existing = await _get_feedback_by_client_uuid(
            db,
            data.child_id,
            data.client_uuid,
        )
        if existing is None:
            raise exc
        if not _feedback_matches(
            existing,
            emotion_record_id=emotion_record_id,
            activity_id=data.activity_id,
            helped=data.helped,
            recorded_at=recorded_at,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet identifiant client désigne un autre retour.",
            ) from exc
        return _feedback_payload(existing, data.record_client_uuid)

    return _feedback_payload(feedback, data.record_client_uuid)
