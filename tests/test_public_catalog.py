"""The anonymous catalog may contain only shared, non-family content."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import get_db
from app.modules.communication.router import router as pictos_router
from app.modules.stories.router import router as stories_router


class CatalogDb:
    def __init__(self, items, *, detail=False):
        self.items = items
        self.detail = detail
        self.statements = []

    async def execute(self, statement):
        self.statements.append(
            str(statement.compile(compile_kwargs={"literal_binds": True}))
        )
        items = self.items
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: items),
            scalar_one_or_none=lambda: items[0] if items else None,
        )


def client_for(db):
    app = FastAPI()
    app.include_router(stories_router, prefix="/stories")
    app.include_router(pictos_router, prefix="/pictos")

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def assert_shared_only_query(sql, table):
    assert f"{table}.owner_id IS NULL" in sql
    assert f"{table}.child_id IS NULL" in sql
    assert f"{table}.is_custom IS false" in sql or f"{table}.is_default IS true" in sql


def test_anonymous_story_list_contains_no_family_metadata():
    db = CatalogDb([
        SimpleNamespace(
            id=11,
            title="Je vais à l'école",
            description="Une histoire",
            category="school",
            cover_url="/storage/pictos/shared/cover.png",
            is_offline_available=True,
            total_pages=3,
        )
    ])
    response = client_for(db).get("/stories/public?category=school")

    assert response.status_code == 200
    assert response.json() == [{
        "id": 11,
        "title": "Je vais à l'école",
        "description": "Une histoire",
        "cover_url": "/storage/pictos/shared/cover.png",
        "category": "school",
        "is_offline_available": True,
        "total_pages": 3,
    }]
    assert_shared_only_query(db.statements[0], "stories")
    assert "stories.category = 'school'" in db.statements[0]


def test_anonymous_story_detail_excludes_private_media_and_private_story():
    choice = SimpleNamespace(
        id=91,
        label="Je demande de l'aide",
        pictogram_url="/storage/pictos/shared/help.png",
        next_page_number=2,
        sort_order=0,
    )
    page = SimpleNamespace(
        id=51,
        page_number=1,
        text="Je suis à l'école.",
        image_url="/stories/media/123",
        pictogram_url="/storage/pictos/shared/school.png",
        audio_url="/storage/audio/story.mp3",
        animation_type="fade",
        local_page_key=None,
        next_page_number=2,
        choices=[choice],
    )
    db = CatalogDb([
        SimpleNamespace(
            id=11,
            title="Je vais à l'école",
            description="",
            category="school",
            cover_url="/stories/media/123",
            is_offline_available=True,
            total_pages=2,
            pages=[page],
        )
    ])
    response = client_for(db).get("/stories/public/11")

    assert response.status_code == 200
    payload = response.json()
    assert payload["cover_url"] == ""
    assert payload["pages"][0]["image_url"] is None
    assert payload["pages"][0]["pictogram_url"] == "/storage/pictos/shared/school.png"
    assert payload["pages"][0]["choices"][0]["label"] == "Je demande de l'aide"
    assert "owner_id" not in payload
    assert "child_id" not in payload
    assert "is_favorite" not in payload
    assert_shared_only_query(db.statements[0], "stories")

    missing = client_for(CatalogDb([])).get("/stories/public/99")
    assert missing.status_code == 404


def test_anonymous_pictogram_catalog_filters_both_pictos_and_categories():
    db = CatalogDb([
        SimpleNamespace(
            id=42,
            category_id=4,
            label="Bonjour",
            image_url="/storage/pictos/bonjour.png",
            audio_url="/storage/audio/pictos/bonjour.mp3",
        )
    ])
    response = client_for(db).get("/pictos/public?category_id=4")

    assert response.status_code == 200
    assert response.json() == [{
        "id": 42,
        "category_id": 4,
        "label": "Bonjour",
        "image_url": "/storage/pictos/bonjour.png",
        "audio_url": "/storage/audio/pictos/bonjour.mp3",
        "is_default": True,
    }]
    assert_shared_only_query(db.statements[0], "pictograms")
    assert_shared_only_query(db.statements[0], "picto_categories")
    assert "pictograms.category_id = 4" in db.statements[0]


def test_anonymous_categories_exclude_custom_and_private_icon():
    db = CatalogDb([
        SimpleNamespace(
            id=4,
            name="École",
            icon_url="/pictos/media/123",
            color="#AABBCC",
            order=2,
        )
    ])
    response = client_for(db).get("/pictos/public/categories")

    assert response.status_code == 200
    assert response.json() == [{
        "id": 4,
        "name": "École",
        "icon_url": "",
        "color": "#AABBCC",
        "order": 2,
        "is_default": True,
    }]
    assert_shared_only_query(db.statements[0], "picto_categories")


@pytest.mark.parametrize("url", [
    "/stories/media/123",
    "/pictos/media/123",
    "https://example.com/private.png",
])
def test_public_catalog_does_not_return_non_public_pictogram_urls(url):
    db = CatalogDb([
        SimpleNamespace(
            id=42,
            category_id=4,
            label="Bonjour",
            image_url=url,
            audio_url="",
        )
    ])
    response = client_for(db).get("/pictos/public")
    assert response.status_code == 200
    assert response.json()[0]["image_url"] == ""
