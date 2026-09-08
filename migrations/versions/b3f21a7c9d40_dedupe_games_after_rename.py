"""dedupe games created by a seed run before the rename migration

`seed_games()` retrouve les jeux par leur titre. Si le seed est lancé avant
que la migration de renommage `a1c7d4e93b28` n'ait tourné, il ne trouve pas
« Retrouve l'image » ni « Trouve l'intrus » et **crée deux nouveaux jeux**,
à côté de « Spot les différences » et « Classe les objets » restés en place.
Le catalogue passe alors de 11 à 13 entrées, et le renommage produit ensuite
deux paires de doublons.

Cette migration répare le cas : pour chaque titre en double dans une même
catégorie, elle garde la ligne d'`id` le plus bas — celle d'origine, à
laquelle la progression des enfants est rattachée — et supprime les autres.
Sur une base saine, elle ne fait rien.

`game_scores` et `game_progress` référencent `games.id` en ON DELETE CASCADE :
la progression éventuellement enregistrée sur un doublon disparaît avec lui.
C'est le comportement voulu, ces doublons n'ayant existé qu'entre un seed
prématuré et le redémarrage suivant.

Revision ID: b3f21a7c9d40
Revises: a1c7d4e93b28
Create Date: 2026-09-08 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3f21a7c9d40'
down_revision: Union[str, Sequence[str], None] = 'a1c7d4e93b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM games AS doublon
        USING games AS garde
        WHERE doublon.title = garde.title
          AND doublon.category_id = garde.category_id
          AND doublon.id > garde.id
        """
    )


def downgrade() -> None:
    # Les doublons supprimés étaient des lignes accidentelles : rien à
    # recréer. Le seed les régénérerait de toute façon s'il était relancé
    # avant un renommage.
    pass
