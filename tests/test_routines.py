from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.modules.auth.models import User  # noqa: F401 - registers ORM relation
from app.modules.children.service import DEFAULT_ROUTINES, _create_default_routines
from app.modules.routines.models import Routine, RoutineStep
from app.modules.routines.schemas import (
    RoutineCreate,
    RoutineResponse,
    RoutineStepSync,
    RoutineUpdate,
)
from app.modules.routines.service import (
    _check_child_ownership,
    _get_routine_owned_by,
    create_routine,
    delete_routine,
    ensure_step_is_current,
    reset_routine,
    sync_custom_step,
    update_routine,
    validate_step,
)


def _routine_with_three_steps():
    steps = [
        SimpleNamespace(id=11, order=1, is_completed=False),
        SimpleNamespace(id=12, order=2, is_completed=False),
        SimpleNamespace(id=13, order=3, is_completed=False),
    ]
    return SimpleNamespace(steps=steps), steps


def test_routine_payload_normalizes_titles_and_requires_contiguous_steps():
    routine = RoutineCreate.model_validate(
        {
            "child_id": 7,
            "title": "  Routine   du matin ",
            "type": "custom",
            "steps": [
                {"order": 1, "title": "  Se   lever "},
                {"order": 2, "title": "Se brosser les dents"},
            ],
        }
    )

    assert routine.title == "Routine du matin"
    assert routine.steps[0].title == "Se lever"

    with pytest.raises(ValidationError):
        RoutineCreate.model_validate(
            {
                "child_id": 7,
                "title": "Routine invalide",
                "type": "custom",
                "steps": [
                    {"order": 1, "title": "Première"},
                    {"order": 3, "title": "Troisième"},
                ],
            }
        )


def test_current_step_is_accepted_and_completed_replay_is_idempotent():
    routine, steps = _routine_with_three_steps()

    assert ensure_step_is_current(routine, steps[0]) is True
    steps[0].is_completed = True
    assert ensure_step_is_current(routine, steps[0]) is False
    assert ensure_step_is_current(routine, steps[1]) is True


def test_skipping_a_routine_step_is_rejected():
    routine, steps = _routine_with_three_steps()

    with pytest.raises(HTTPException) as error:
        ensure_step_is_current(routine, steps[1])

    assert error.value.status_code == status.HTTP_409_CONFLICT


def _mapped_routine(
    *,
    routine_type="school",
    is_default=True,
    step_count=2,
    completed_orders=(),
):
    routine = Routine(
        id=41,
        child_id=7,
        title="Routine école",
        type=routine_type,
        is_active=True,
        is_default=is_default,
    )
    routine.steps = [
        RoutineStep(
            id=100 + order,
            routine_id=routine.id,
            order=order,
            title=f"Étape {order}",
            is_completed=order in completed_orders,
            is_default=is_default,
            client_uuid=None,
        )
        for order in range(1, step_count + 1)
    ]
    return routine


def _mutation_db():
    return SimpleNamespace(
        add=MagicMock(),
        delete=AsyncMock(),
        flush=AsyncMock(),
    )


def test_only_custom_routines_can_be_created_and_type_is_immutable():
    with pytest.raises(ValidationError):
        RoutineCreate.model_validate(
            {
                "child_id": 7,
                "title": "Fausse routine système",
                "type": "school",
            }
        )

    with pytest.raises(ValidationError):
        RoutineUpdate.model_validate({"type": "custom"})


def test_custom_step_payload_is_normalized_and_strictly_validated():
    payload = RoutineStepSync.model_validate(
        {
            "client_uuid": "routine-step-001",
            "title": "  Mettre   les chaussures  ",
        }
    )
    assert payload.title == "Mettre les chaussures"

    with pytest.raises(ValidationError):
        RoutineStepSync.model_validate(
            {"client_uuid": "routine-step-002", "title": "   "}
        )
    with pytest.raises(ValidationError):
        RoutineStepSync.model_validate(
            {"client_uuid": "x" * 65, "title": "Étape"}
        )
    with pytest.raises(ValidationError):
        RoutineStepSync.model_validate(
            {"client_uuid": "uuid avec espaces", "title": "Étape"}
        )


@pytest.mark.asyncio
async def test_created_routine_and_initial_steps_are_always_custom():
    added = []

    def add(instance):
        if isinstance(instance, Routine) and instance.id is None:
            instance.id = 71
        added.append(instance)

    db = SimpleNamespace(add=add, flush=AsyncMock())
    data = RoutineCreate.model_validate(
        {
            "child_id": 7,
            "title": "Ma routine",
            "steps": [{"order": 1, "title": "Mon étape"}],
        }
    )
    returned = SimpleNamespace(id=71)

    with (
        patch(
            "app.modules.routines.service._check_child_ownership",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.routines.service._get_routine_owned_by",
            new=AsyncMock(return_value=returned),
        ),
    ):
        result = await create_routine(db, data, parent_id=9)

    routine = next(item for item in added if isinstance(item, Routine))
    step = next(item for item in added if isinstance(item, RoutineStep))
    assert result is returned
    assert routine.type == "custom"
    assert routine.is_default is False
    assert step.is_default is False


@pytest.mark.asyncio
async def test_child_ownership_rejects_another_parent():
    result = MagicMock()
    result.scalar_one_or_none.return_value = SimpleNamespace(parent_id=22)
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    with pytest.raises(HTTPException) as error:
        await _check_child_ownership(db, child_id=7, parent_id=21)

    assert error.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_child_ownership_returns_not_found_for_unknown_child():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    with pytest.raises(HTTPException) as error:
        await _check_child_ownership(db, child_id=404, parent_id=21)

    assert error.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_foreign_routine_is_rejected_before_for_update():
    child_id_result = MagicMock()
    child_id_result.scalar_one_or_none.return_value = 7
    child_result = MagicMock()
    child_result.scalar_one_or_none.return_value = SimpleNamespace(parent_id=22)
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[child_id_result, child_result])
    )

    with pytest.raises(HTTPException) as error:
        await _get_routine_owned_by(
            db,
            routine_id=41,
            parent_id=21,
            lock=True,
        )

    assert error.value.status_code == status.HTTP_403_FORBIDDEN
    assert db.execute.await_count == 2
    assert all(
        "FOR UPDATE" not in str(invocation.args[0]).upper()
        for invocation in db.execute.await_args_list
    )


@pytest.mark.asyncio
async def test_locked_routine_disappearance_is_reported_after_ownership_check():
    child_id_result = MagicMock()
    child_id_result.scalar_one_or_none.return_value = 7
    child_result = MagicMock()
    child_result.scalar_one_or_none.return_value = SimpleNamespace(parent_id=21)
    locked_result = MagicMock()
    locked_result.scalar_one_or_none.return_value = None
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[child_id_result, child_result, locked_result]
        )
    )

    with pytest.raises(HTTPException) as error:
        await _get_routine_owned_by(
            db,
            routine_id=41,
            parent_id=21,
            lock=True,
        )

    assert error.value.status_code == status.HTTP_404_NOT_FOUND
    assert db.execute.await_count == 3
    locked_statement = db.execute.await_args_list[2].args[0]
    assert "FOR UPDATE" in str(locked_statement).upper()


@pytest.mark.asyncio
async def test_default_routine_cannot_be_updated_or_deleted():
    routine = _mapped_routine()
    db = _mutation_db()
    get_owned = AsyncMock(return_value=routine)

    with patch(
        "app.modules.routines.service._get_routine_owned_by",
        new=get_owned,
    ):
        with pytest.raises(HTTPException) as update_error:
            await update_routine(
                db,
                routine.id,
                RoutineUpdate(title="Nouveau titre"),
                parent_id=9,
            )
        with pytest.raises(HTTPException) as delete_error:
            await delete_routine(db, routine.id, parent_id=9)

    assert update_error.value.status_code == status.HTTP_409_CONFLICT
    assert delete_error.value.status_code == status.HTTP_409_CONFLICT
    assert get_owned.await_args_list == [
        call(db, routine.id, 9, lock=True),
        call(db, routine.id, 9, lock=True),
    ]
    db.flush.assert_not_awaited()
    db.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_custom_legacy_routine_is_protected_even_if_flag_is_wrong():
    routine = _mapped_routine(is_default=False, routine_type="morning")
    db = _mutation_db()

    with patch(
        "app.modules.routines.service._get_routine_owned_by",
        new=AsyncMock(return_value=routine),
    ):
        with pytest.raises(HTTPException) as error:
            await delete_routine(db, routine.id, parent_id=9)

    assert error.value.status_code == status.HTTP_409_CONFLICT
    db.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_custom_routine_can_be_updated_and_deleted():
    routine = _mapped_routine(is_default=False, routine_type="custom")
    db = _mutation_db()
    get_owned = AsyncMock(return_value=routine)

    with patch(
        "app.modules.routines.service._get_routine_owned_by",
        new=get_owned,
    ):
        updated = await update_routine(
            db,
            routine.id,
            RoutineUpdate(title="  Ma   routine "),
            parent_id=9,
        )
        await delete_routine(db, routine.id, parent_id=9)

    assert updated.title == "Ma routine"
    assert get_owned.await_args_list == [
        call(db, routine.id, 9, lock=True),
        call(db, routine.id, 9, lock=True),
    ]
    db.flush.assert_awaited_once()
    db.delete.assert_awaited_once_with(routine)


@pytest.mark.asyncio
async def test_validation_serializes_on_the_owned_routine():
    routine = _mapped_routine(completed_orders=(1,))
    validated_step = routine.steps[0]
    step_result = MagicMock()
    step_result.scalar_one_or_none.return_value = validated_step
    db = _mutation_db()
    db.execute = AsyncMock(return_value=step_result)
    get_owned = AsyncMock(return_value=routine)

    with patch(
        "app.modules.routines.service._get_routine_owned_by",
        new=get_owned,
    ):
        result = await validate_step(
            db,
            routine.id,
            validated_step.id,
            parent_id=9,
        )

    get_owned.assert_awaited_once_with(db, routine.id, 9, lock=True)
    assert result["step_id"] == validated_step.id
    assert result["steps_completed"] == 1


@pytest.mark.asyncio
async def test_reset_serializes_on_the_owned_routine():
    routine = _mapped_routine(completed_orders=(1,))
    session_result = MagicMock()
    session_result.scalars.return_value.all.return_value = []
    db = _mutation_db()
    db.execute = AsyncMock(return_value=session_result)
    get_owned = AsyncMock(return_value=routine)

    with patch(
        "app.modules.routines.service._get_routine_owned_by",
        new=get_owned,
    ):
        result = await reset_routine(db, routine.id, parent_id=9)

    get_owned.assert_awaited_once_with(db, routine.id, 9, lock=True)
    assert result is routine
    assert all(step.is_completed is False for step in routine.steps)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_custom_step_is_appended_to_a_default_routine():
    routine = _mapped_routine()
    db = _mutation_db()
    get_owned = AsyncMock(return_value=routine)
    payload = RoutineStepSync(
        client_uuid="routine-step-append-001",
        title="Préparer le goûter",
        image_url="/media/gouter.png",
    )

    with patch(
        "app.modules.routines.service._get_routine_owned_by",
        new=get_owned,
    ):
        step = await sync_custom_step(
            db,
            routine.id,
            payload,
            parent_id=9,
        )

    get_owned.assert_awaited_once_with(db, routine.id, 9, lock=True)
    assert step.order == 3
    assert step.routine_id == routine.id
    assert step.title == "Préparer le goûter"
    assert step.is_completed is False
    assert step.is_default is False
    assert step.client_uuid == "routine-step-append-001"
    assert routine.steps[-1] is step
    db.add.assert_called_once_with(step)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_custom_step_replay_is_idempotent_even_after_progress():
    routine = _mapped_routine(completed_orders=(1,))
    existing = RoutineStep(
        id=501,
        routine_id=routine.id,
        order=3,
        title="Préparer le goûter",
        image_url=None,
        audio_url=None,
        is_completed=False,
        is_default=False,
        client_uuid="routine-step-replay-001",
    )
    routine.steps.append(existing)
    db = _mutation_db()

    with patch(
        "app.modules.routines.service._get_routine_owned_by",
        new=AsyncMock(return_value=routine),
    ):
        replay = await sync_custom_step(
            db,
            routine.id,
            RoutineStepSync(
                client_uuid="routine-step-replay-001",
                title="Préparer le goûter",
            ),
            parent_id=9,
        )

    assert replay is existing
    db.add.assert_not_called()
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_custom_step_uuid_collision_is_rejected():
    routine = _mapped_routine()
    routine.steps.append(
        RoutineStep(
            id=501,
            routine_id=routine.id,
            order=3,
            title="Préparer le goûter",
            is_completed=False,
            is_default=False,
            client_uuid="routine-step-collision-001",
        )
    )
    db = _mutation_db()

    with patch(
        "app.modules.routines.service._get_routine_owned_by",
        new=AsyncMock(return_value=routine),
    ):
        with pytest.raises(HTTPException) as error:
            await sync_custom_step(
                db,
                routine.id,
                RoutineStepSync(
                    client_uuid="routine-step-collision-001",
                    title="Un autre contenu",
                ),
                parent_id=9,
            )

    assert error.value.status_code == status.HTTP_409_CONFLICT
    db.add.assert_not_called()
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_step_is_rejected_while_routine_has_progress():
    routine = _mapped_routine(completed_orders=(1,))
    db = _mutation_db()

    with patch(
        "app.modules.routines.service._get_routine_owned_by",
        new=AsyncMock(return_value=routine),
    ):
        with pytest.raises(HTTPException) as error:
            await sync_custom_step(
                db,
                routine.id,
                RoutineStepSync(
                    client_uuid="routine-step-progress-001",
                    title="Nouvelle étape",
                ),
                parent_id=9,
            )

    assert error.value.status_code == status.HTTP_409_CONFLICT
    assert "Recommencez" in error.value.detail
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_new_step_is_rejected_at_twenty_step_limit():
    routine = _mapped_routine(step_count=20)
    db = _mutation_db()

    with patch(
        "app.modules.routines.service._get_routine_owned_by",
        new=AsyncMock(return_value=routine),
    ):
        with pytest.raises(HTTPException) as error:
            await sync_custom_step(
                db,
                routine.id,
                RoutineStepSync(
                    client_uuid="routine-step-limit-001",
                    title="Étape 21",
                ),
                parent_id=9,
            )

    assert error.value.status_code == status.HTTP_409_CONFLICT
    assert "20 étapes" in error.value.detail
    db.add.assert_not_called()


def test_routine_responses_expose_protection_and_sync_fields():
    routine = _mapped_routine(step_count=1)

    response = RoutineResponse.model_validate(routine)

    assert response.is_default is True
    assert response.steps[0].is_default is True
    assert response.steps[0].client_uuid is None


@pytest.mark.asyncio
async def test_default_routine_factory_marks_routines_and_steps_as_protected():
    added = []
    next_id = 1

    def add(instance):
        nonlocal next_id
        if isinstance(instance, Routine) and instance.id is None:
            instance.id = next_id
            next_id += 1
        added.append(instance)

    db = SimpleNamespace(add=add, flush=AsyncMock())

    await _create_default_routines(db, child_id=7)

    routines = [item for item in added if isinstance(item, Routine)]
    steps = [item for item in added if isinstance(item, RoutineStep)]
    assert len(routines) == len(DEFAULT_ROUTINES) == 3
    assert all(routine.is_default is True for routine in routines)
    assert all(routine.type != "custom" for routine in routines)
    assert len(steps) == sum(len(item["steps"]) for item in DEFAULT_ROUTINES)
    assert all(step.is_default is True for step in steps)


def test_migration_normalizes_legacy_orders_before_constraints():
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "e4f6a8b0c2d4_protect_default_routines.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    ranking_position = migration.index("ROW_NUMBER() OVER")
    unique_position = migration.index('"uq_routine_steps_routine_order"')
    check_position = migration.index('"ck_routine_steps_order_positive"')

    assert 'PARTITION BY routine_id' in migration
    assert 'CASE WHEN \"order\" >= 1 THEN 0 ELSE 1 END' in migration
    assert ranking_position < unique_position < check_position
