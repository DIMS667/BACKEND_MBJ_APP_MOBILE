"""dedupe catalog stories sharing a title

`seed_stories()` retrouve les histoires **par leur titre** et n'en attend
qu'une seule (`scalar_one_or_none`). Deux exécutions concurrentes du seed
peuvent chacune ne rien trouver, puis insérer : la base se retrouve avec
deux lignes de même titre, et l'application affiche l'histoire en double
dans la liste. C'est ce qui a été constaté en production sur « Une nouvelle
personne arrive ».

Cette migration garde, pour chaque titre en double, la ligne d'`id` le plus
bas — la première créée, celle à laquelle la progression de lecture des
enfants est rattachée — et supprime les autres. Sur une base saine, elle ne
fait rien.

Elle ne touche **que les histoires du catalogue** : `is_custom = false` et
aucun propriétaire. Une histoire personnalisée créée par un parent peut
légitimement porter le même titre qu'une histoire du catalogue ; la
supprimer serait une perte de contenu.

`story_pages`, `story_choices`, `story_progress`, `story_favorites` et
`story_media` référencent l'histoire en ON DELETE CASCADE : les lignes
rattachées au doublon partent avec lui.

Revision ID: c5d83e11f742
Revises: b3f21a7c9d40
Create Date: 2026-09-10 05:10:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c5d83e11f742'
down_revision: Union[str, Sequence[str], None] = 'b3f21a7c9d40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM stories AS doublon
        USING stories AS garde
        WHERE doublon.title = garde.title
          AND doublon.id > garde.id
          AND COALESCE(doublon.is_custom, false) = false
          AND COALESCE(garde.is_custom, false) = false
          AND doublon.owner_id IS NULL
          AND garde.owner_id IS NULL
          AND doublon.child_id IS NULL
          AND garde.child_id IS NULL
        """
    )


def downgrade() -> None:
    # Les lignes supprimées étaient des insertions accidentelles : il n'y a
    # rien à recréer. Le seed régénère l'histoire si elle venait à manquer.
    pass
