from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.modules.communication.schemas import (
    CustomCategoryUpsert,
    CustomPictogramUpsert,
)
from app.modules.communication.service import (
    delete_custom_category,
    rank_suggestion_ids,
    validate_image_signature,
)


def test_custom_category_normalizes_name_and_validates_color():
    category = CustomCategoryUpsert.model_validate(
        {
            "client_uuid": "category-client-001",
            "child_id": 7,
            "name": "  Mes   activités  ",
            "color": "#2A9D8F",
        }
    )

    assert category.name == "Mes activités"
    assert category.color == "#2A9D8F"

    with pytest.raises(ValidationError):
        CustomCategoryUpsert.model_validate(
            {
                "client_uuid": "category-client-002",
                "child_id": 7,
                "name": "Maison",
                "color": "blue",
            }
        )


def test_custom_pictogram_requires_a_private_media_url():
    valid = CustomPictogramUpsert.model_validate(
        {
            "client_uuid": "pictogram-client-001",
            "child_id": 7,
            "category_id": 3,
            "label": "  Mon   cartable ",
            "image_url": "/pictos/media/42",
        }
    )
    assert valid.label == "Mon cartable"

    with pytest.raises(ValidationError):
        CustomPictogramUpsert.model_validate(
            {
                "client_uuid": "pictogram-client-002",
                "child_id": 7,
                "category_id": 3,
                "label": "Cartable",
                "image_url": "https://example.org/public.jpg",
            }
        )


@pytest.mark.parametrize(
    ("content", "content_type", "expected"),
    [
        (b"\xff\xd8\xff\x00jpeg", "image/jpeg", True),
        (b"\x89PNG\r\n\x1a\nrest", "image/png", True),
        (b"RIFF\x08\x00\x00\x00WEBPrest", "image/webp", True),
        (b"<script>alert(1)</script>", "image/jpeg", False),
        (b"\x89PNGbad", "image/png", False),
        (b"GIF89a", "image/gif", False),
    ],
)
def test_image_signature_validation(content, content_type, expected):
    assert validate_image_signature(content, content_type) is expected


def test_contextual_ranking_prefers_recent_learned_transitions():
    histories = [
        [1, 4, 8],
        [1, 4, 9],
        [1, 2, 7],
        [3, 4, 8],
    ]

    assert rank_suggestion_ids(histories, 1, 3) == [4, 2]
    assert rank_suggestion_ids(histories, 4, 3) == [8, 9]
    assert 4 not in rank_suggestion_ids(histories, 4, 6)


@pytest.mark.asyncio
async def test_custom_category_deletion_removes_owned_category():
    category = SimpleNamespace(id=31, is_default=False, child_id=7)
    pictogram = SimpleNamespace(
        is_default=False,
        owner_id=4,
        child_id=7,
        image_url="",
    )
    category_result = MagicMock()
    category_result.scalar_one_or_none.return_value = category
    pictogram_result = MagicMock()
    pictogram_result.scalars.return_value.all.return_value = [pictogram]
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[category_result, pictogram_result]),
        delete=AsyncMock(),
        flush=AsyncMock(),
    )

    await delete_custom_category(db, "category-client-031", parent_id=4)

    db.delete.assert_awaited_once_with(category)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_default_category_deletion_is_rejected():
    category_result = MagicMock()
    category_result.scalar_one_or_none.return_value = SimpleNamespace(
        id=1,
        is_default=True,
        child_id=None,
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=category_result),
        delete=AsyncMock(),
        flush=AsyncMock(),
    )

    with pytest.raises(HTTPException) as error:
        await delete_custom_category(db, "protected-category", parent_id=4)

    assert error.value.status_code == status.HTTP_409_CONFLICT
    db.delete.assert_not_awaited()
