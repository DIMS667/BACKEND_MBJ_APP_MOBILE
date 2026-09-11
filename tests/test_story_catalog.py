import pytest
from pydantic import ValidationError

from app.modules.stories.schemas import StoryCatalogEntry
from app.modules.stories.story_catalog import STORIES_SPRINT_1_DATA


def _validate(story: dict, index: int = 0) -> StoryCatalogEntry:
    return StoryCatalogEntry.model_validate(story)


def test_catalog_covers_all_social_themes():
    stories = [_validate(story, index) for index, story in enumerate(STORIES_SPRINT_1_DATA)]

    assert len(stories) == 14
    assert {story.category for story in stories} == {
        "school",
        "doctor",
        "emotions",
        "change",
        "frustration",
        "sleep",
        "hygiene",
    }
    assert all(len(story.pages) >= 5 for story in stories)


def test_catalog_stories_are_all_interactive():
    # Chaque histoire doit demander une intervention de l'enfant (au moins
    # un choix) : plus d'histoires purement passives dans le catalogue.
    for index, raw_story in enumerate(STORIES_SPRINT_1_DATA):
        story = _validate(raw_story, index)
        has_choice = any(page.choices for page in story.pages)
        assert has_choice, f"'{story.title}' n'a aucun choix interactif"


def test_catalog_choices_only_move_forward_to_existing_pages():
    choice_count = 0
    for index, raw_story in enumerate(STORIES_SPRINT_1_DATA):
        story = _validate(raw_story, index)
        for page in story.pages:
            assert page.pictogram_url and "static.arasaac.org/pictograms/" in page.pictogram_url
            for choice in page.choices:
                choice_count += 1
                assert page.page_number < choice.next_page_number <= len(story.pages)

    assert choice_count >= 14


@pytest.mark.parametrize(
    "pages",
    [
        [
            {"page_number": 1, "text": "Début", "next_page_number": 1},
            {"page_number": 2, "text": "Fin"},
        ],
        [
            {
                "page_number": 1,
                "text": "Début",
                "choices": [{"label": "Retour", "next_page_number": 1}],
            },
            {"page_number": 2, "text": "Fin"},
        ],
        [
            {"page_number": 1, "text": "Début"},
            {"page_number": 3, "text": "Page manquante"},
        ],
    ],
)
def test_catalog_graph_rejects_loops_and_missing_pages(pages):
    with pytest.raises(ValidationError):
        StoryCatalogEntry.model_validate(
            {
                "title": "Une histoire invalide",
                "description": "Test",
                "category": "custom",
                "pages": pages,
            }
        )
