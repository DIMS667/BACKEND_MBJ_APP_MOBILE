from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.modules.auth.models import User  # noqa: F401 - configures ORM relations
from app.modules.emotions.schemas import (
    CalmingFeedbackSync,
    EmotionRecordCreate,
    EmotionRecordSync,
)
from app.modules.emotions.service import (
    get_personalized_calming_activities,
    parse_legacy_context,
    rank_calming_activities,
    sync_calming_feedback,
    sync_emotion,
)
from app.shared.seed import CALMING_ACTIVITIES_DATA
from app.websocket.manager import manager


RECORDED_AT = datetime(2026, 8, 10, 14, 35, tzinfo=timezone.utc)


def _scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    return result


def _activity(activity_id: int, display_order: int):
    return SimpleNamespace(
        id=activity_id,
        name=f"Activité {activity_id}",
        type="breathing",
        description="Une activité douce.",
        content_url=None,
        duration_seconds=60,
        icon_url=None,
        display_order=display_order,
        is_active=True,
    )


def _sync_payload(**overrides) -> EmotionRecordSync:
    payload = {
        "client_uuid": "emotion-client-001",
        "child_id": 7,
        "emotion_id": 3,
        "context_key": "bruit",
        "intensity": "fort",
        "recorded_at": RECORDED_AT,
    }
    payload.update(overrides)
    return EmotionRecordSync.model_validate(payload)


def test_emotion_payload_validates_structured_fields_and_keeps_legacy_compatibility():
    payload = _sync_payload()

    assert payload.context_key == "bruit"
    assert payload.intensity == "fort"
    assert payload.recorded_at == RECORDED_AT
    assert _sync_payload(context_key="seul").context_key == "seul"

    legacy = EmotionRecordCreate.model_validate(
        {
            "child_id": 7,
            "emotion_id": 3,
            "context": "bruit|intensité:doux",
        }
    )
    assert legacy.client_uuid is None
    assert parse_legacy_context(legacy.context) == ("bruit", "doux")

    with pytest.raises(ValidationError):
        _sync_payload(intensity="énorme")
    with pytest.raises(ValidationError):
        _sync_payload(recorded_at=datetime(2026, 8, 10, 14, 35))
    with pytest.raises(ValidationError):
        _sync_payload(
            recorded_at=datetime.now(timezone.utc) + timedelta(minutes=10)
        )


def test_legacy_context_does_not_invent_intensity_or_time_context():
    assert parse_legacy_context("maison") == ("maison", None)
    assert parse_legacy_context("seul") == ("seul", None)
    assert parse_legacy_context("matin|intensité:moyen") == (None, "moyen")
    assert parse_legacy_context(None) == (None, None)


def test_calming_feedback_requires_explicit_boolean_and_stable_record_uuid():
    feedback = CalmingFeedbackSync.model_validate(
        {
            "client_uuid": "feedback-client-001",
            "child_id": 7,
            "record_client_uuid": "emotion-client-001",
            "activity_id": 2,
            "helped": False,
            "recorded_at": RECORDED_AT,
        }
    )
    assert feedback.helped is False

    with pytest.raises(ValidationError):
        CalmingFeedbackSync.model_validate(
            {
                "client_uuid": "feedback-client-002",
                "child_id": 7,
                "record_client_uuid": "short",
                "activity_id": 2,
                "recorded_at": RECORDED_AT,
            }
        )


def test_editorial_order_is_stable_without_history_and_one_feedback_is_gentle():
    activities = [_activity(1, 1), _activity(2, 2), _activity(3, 3)]

    no_history = rank_calming_activities(activities, {})
    one_feedback = rank_calming_activities(
        activities,
        {3: {"feedback_count": 1, "helped_count": 1}},
    )

    assert [item["id"] for item in no_history] == [1, 2, 3]
    assert [item["id"] for item in one_feedback] == [3, 1, 2]
    assert one_feedback[0]["personalization_score"] == 0.666667
    assert all(item["personalized"] is False for item in one_feedback)


def test_personalization_is_progressive_and_never_hides_an_activity():
    activities = [_activity(1, 1), _activity(2, 2), _activity(3, 3)]
    ranked = rank_calming_activities(
        activities,
        {
            2: {
                "feedback_count": 2,
                "helped_count": 0,
                "last_helped_at": None,
            },
            3: {
                "feedback_count": 2,
                "helped_count": 2,
                "last_helped_at": RECORDED_AT,
            },
        },
    )

    assert [item["id"] for item in ranked] == [3, 1, 2]
    assert {item["id"] for item in ranked} == {1, 2, 3}
    assert ranked[0]["personalization_score"] == 0.75
    assert ranked[-1]["personalization_score"] == 0.25
    assert ranked[0]["personalized"] is True
    assert ranked[-1]["personalized"] is False


def test_seed_appends_four_soft_activities_without_reordering_existing_ones():
    assert [item["name"] for item in CALMING_ACTIVITIES_DATA[:4]] == [
        "Respiration douce",
        "Musique apaisante",
        "Animation relaxante",
        "Jeu calme",
    ]
    assert len(CALMING_ACTIVITIES_DATA) == 8
    assert [item["display_order"] for item in CALMING_ACTIVITIES_DATA] == list(
        range(1, 9)
    )
    assert {item["type"] for item in CALMING_ACTIVITIES_DATA[4:]} == {
        "sensory",
        "movement",
        "grounding",
        "quiet",
    }


@pytest.mark.asyncio
async def test_emotion_sync_replay_is_idempotent_and_emits_no_second_event(
    monkeypatch,
):
    payload = _sync_payload()
    existing = SimpleNamespace(
        id=41,
        child_id=7,
        emotion_id=3,
        client_uuid=payload.client_uuid,
        context=None,
        context_key="bruit",
        intensity="fort",
        recorded_at=RECORDED_AT,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _scalar_result(SimpleNamespace(id=7, parent_id=4)),
                _scalar_result(existing),
            ]
        ),
        add=MagicMock(),
        flush=AsyncMock(),
        rollback=AsyncMock(),
    )
    send_event = AsyncMock()
    monkeypatch.setattr(manager, "send_to_child", send_event)

    result = await sync_emotion(db, payload, parent_id=4)

    assert result is existing
    db.add.assert_not_called()
    db.flush.assert_not_awaited()
    send_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_emotion_sync_rejects_a_divergent_uuid_collision():
    payload = _sync_payload(emotion_id=3)
    existing = SimpleNamespace(
        id=41,
        child_id=7,
        emotion_id=2,
        client_uuid=payload.client_uuid,
        context=None,
        context_key="bruit",
        intensity="fort",
        recorded_at=RECORDED_AT,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _scalar_result(SimpleNamespace(id=7, parent_id=4)),
                _scalar_result(existing),
            ]
        ),
        add=MagicMock(),
        flush=AsyncMock(),
        rollback=AsyncMock(),
    )

    with pytest.raises(HTTPException) as error:
        await sync_emotion(db, payload, parent_id=4)

    assert error.value.status_code == status.HTTP_409_CONFLICT
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_new_emotion_sync_persists_structured_event_and_emits_once(
    monkeypatch,
):
    payload = _sync_payload()
    emotion = SimpleNamespace(
        id=3,
        name="colère",
        color="#FF6B6B",
        is_positive=False,
    )
    added = []

    def add_record(record):
        record.id = 71
        added.append(record)

    stored_result = MagicMock()
    stored_result.scalar_one.side_effect = lambda: added[0]
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _scalar_result(SimpleNamespace(id=7, parent_id=4)),
                _scalar_result(None),
                _scalar_result(emotion),
                stored_result,
            ]
        ),
        add=MagicMock(side_effect=add_record),
        flush=AsyncMock(),
        rollback=AsyncMock(),
    )
    send_event = AsyncMock()
    monkeypatch.setattr(manager, "send_to_child", send_event)

    result = await sync_emotion(db, payload, parent_id=4)

    assert result.id == 71
    assert result.client_uuid == "emotion-client-001"
    assert result.context_key == "bruit"
    assert result.intensity == "fort"
    assert result.recorded_at == RECORDED_AT
    db.flush.assert_awaited_once()
    send_event.assert_awaited_once()
    assert send_event.await_args.args[1]["data"]["client_uuid"] == payload.client_uuid


@pytest.mark.asyncio
async def test_calming_feedback_replay_is_idempotent():
    payload = CalmingFeedbackSync.model_validate(
        {
            "client_uuid": "feedback-client-001",
            "child_id": 7,
            "record_client_uuid": "emotion-client-001",
            "activity_id": 2,
            "helped": True,
            "recorded_at": RECORDED_AT,
        }
    )
    emotion_record = SimpleNamespace(id=41, client_uuid="emotion-client-001")
    existing = SimpleNamespace(
        id=51,
        child_id=7,
        emotion_record_id=41,
        activity_id=2,
        client_uuid="feedback-client-001",
        helped=True,
        recorded_at=RECORDED_AT,
        created_at=RECORDED_AT,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _scalar_result(SimpleNamespace(id=7, parent_id=4)),
                _scalar_result(emotion_record),
                _scalar_result(existing),
            ]
        ),
        add=MagicMock(),
        flush=AsyncMock(),
        rollback=AsyncMock(),
    )

    result = await sync_calming_feedback(db, payload, parent_id=4)

    assert result["id"] == 51
    assert result["record_client_uuid"] == "emotion-client-001"
    db.add.assert_not_called()
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_calming_feedback_rejects_a_divergent_uuid_collision():
    payload = CalmingFeedbackSync.model_validate(
        {
            "client_uuid": "feedback-client-001",
            "child_id": 7,
            "record_client_uuid": "emotion-client-001",
            "activity_id": 2,
            "helped": True,
            "recorded_at": RECORDED_AT,
        }
    )
    emotion_record = SimpleNamespace(id=41, client_uuid="emotion-client-001")
    existing = SimpleNamespace(
        id=51,
        child_id=7,
        emotion_record_id=41,
        activity_id=1,
        client_uuid="feedback-client-001",
        helped=True,
        recorded_at=RECORDED_AT,
        created_at=RECORDED_AT,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _scalar_result(SimpleNamespace(id=7, parent_id=4)),
                _scalar_result(emotion_record),
                _scalar_result(existing),
            ]
        ),
        add=MagicMock(),
        flush=AsyncMock(),
        rollback=AsyncMock(),
    )

    with pytest.raises(HTTPException) as error:
        await sync_calming_feedback(db, payload, parent_id=4)

    assert error.value.status_code == status.HTTP_409_CONFLICT
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_feedback_and_personalization_enforce_child_ownership():
    feedback_payload = CalmingFeedbackSync.model_validate(
        {
            "client_uuid": "feedback-client-001",
            "child_id": 7,
            "record_client_uuid": "emotion-client-001",
            "activity_id": 2,
            "helped": True,
            "recorded_at": RECORDED_AT,
        }
    )
    foreign_child_result = _scalar_result(
        SimpleNamespace(id=7, parent_id=99)
    )
    feedback_db = SimpleNamespace(
        execute=AsyncMock(return_value=foreign_child_result),
        add=MagicMock(),
        flush=AsyncMock(),
    )

    with pytest.raises(HTTPException) as feedback_error:
        await sync_calming_feedback(feedback_db, feedback_payload, parent_id=4)
    assert feedback_error.value.status_code == status.HTTP_403_FORBIDDEN
    feedback_db.add.assert_not_called()

    ranking_db = SimpleNamespace(
        execute=AsyncMock(return_value=foreign_child_result)
    )
    with pytest.raises(HTTPException) as ranking_error:
        await get_personalized_calming_activities(
            ranking_db,
            child_id=7,
            parent_id=4,
        )
    assert ranking_error.value.status_code == status.HTTP_403_FORBIDDEN
    assert ranking_db.execute.await_count == 1
