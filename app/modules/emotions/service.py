from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status
from datetime import datetime, timedelta
from app.modules.children.models import Child
from .models import Emotion, EmotionRecord, CalmingActivity
from .schemas import EmotionRecordCreate


async def _check_child_ownership(db: AsyncSession, child_id: int, parent_id: int) -> None:
    result = await db.execute(select(Child).where(Child.id == child_id))
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enfant introuvable.")
    if child.parent_id != parent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé.")


# ─── Liste des émotions disponibles ──────────────────────────────
async def get_all_emotions(db: AsyncSession) -> list:
    result = await db.execute(select(Emotion).order_by(Emotion.id))
    return list(result.scalars().all())


# ─── Enregistrer une émotion ─────────────────────────────────────
async def save_emotion(
    db: AsyncSession, data: EmotionRecordCreate, parent_id: int
) -> EmotionRecord:
    from app.websocket.manager import manager  # import ici pour éviter circular import
    
    await _check_child_ownership(db, data.child_id, parent_id)

    # Vérifier que l'émotion existe
    result = await db.execute(select(Emotion).where(Emotion.id == data.emotion_id))
    emotion = result.scalar_one_or_none()
    if not emotion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Émotion introuvable.")

    record = EmotionRecord(
        child_id=data.child_id,
        emotion_id=data.emotion_id,
        context=data.context,
    )
    db.add(record)
    await db.flush()

    # ── Événement WebSocket ───────────────────────────────────────
    await manager.send_to_child(data.child_id, {
        "type": "emotion_recorded",
        "data": {
            "child_id": data.child_id,
            "emotion_name": emotion.name,
            "emotion_color": emotion.color,
            "is_positive": emotion.is_positive,
            "context": data.context,
        }
    })

    # Re-fetch avec la relation emotion chargée
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(EmotionRecord)
        .where(EmotionRecord.id == record.id)
        .options(selectinload(EmotionRecord.emotion))
    )
    return result.scalar_one()


# ─── Historique des émotions ─────────────────────────────────────
async def get_emotion_history(
    db: AsyncSession, child_id: int, parent_id: int, limit: int = 30
) -> list:
    await _check_child_ownership(db, child_id, parent_id)

    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(EmotionRecord)
        .options(selectinload(EmotionRecord.emotion))
        .where(EmotionRecord.child_id == child_id)
        .order_by(EmotionRecord.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ─── Statistiques émotionnelles ──────────────────────────────────
async def get_emotion_stats(
    db: AsyncSession, child_id: int, parent_id: int, days: int = 30
) -> dict:
    await _check_child_ownership(db, child_id, parent_id)

    since = datetime.utcnow() - timedelta(days=days)

    # Compter par émotion
    result = await db.execute(
        select(
            Emotion.name,
            Emotion.color,
            func.count(EmotionRecord.id).label("count")
        )
        .join(EmotionRecord, EmotionRecord.emotion_id == Emotion.id)
        .where(
            EmotionRecord.child_id == child_id,
            EmotionRecord.created_at >= since,
        )
        .group_by(Emotion.id, Emotion.name, Emotion.color)
        .order_by(func.count(EmotionRecord.id).desc())
    )
    rows = result.all()

    total = sum(r.count for r in rows)
    stats = [
        {
            "emotion_name": r.name,
            "color": r.color,
            "count": r.count,
            "percentage": round((r.count / total * 100), 1) if total > 0 else 0,
        }
        for r in rows
    ]

    return {
        "child_id": child_id,
        "total_records": total,
        "period_days": days,
        "stats": stats,
        "most_frequent": stats[0]["emotion_name"] if stats else None,
    }


# ─── Activités apaisantes ────────────────────────────────────────
async def get_calming_activities(
    db: AsyncSession, activity_type: str = None
) -> list:
    query = select(CalmingActivity).order_by(CalmingActivity.type)
    if activity_type:
        query = query.where(CalmingActivity.type == activity_type)
    result = await db.execute(query)
    return list(result.scalars().all())