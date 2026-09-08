"""rename misleading game titles

Deux jeux annonçaient une activité qu'ils ne proposaient pas :

- « Spot les différences » (« Trouve les différences entre deux images »)
  servait en réalité la recherche d'une image demandée, exactement comme
  « Trouve l'objet » ;
- « Classe les objets » (« Range les objets dans la bonne catégorie »)
  demandait en fait de repérer l'intrus.

Le renommage se fait ici plutôt que dans le seed : celui-ci retrouve les
jeux par leur titre, donc un simple changement de libellé y aurait créé un
second jeu au lieu de corriger l'existant — laissant un doublon et la
progression des enfants attachée à l'ancienne ligne.

Revision ID: a1c7d4e93b28
Revises: 271f068c41d5
Create Date: 2026-09-06 03:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1c7d4e93b28'
down_revision: Union[str, Sequence[str], None] = '271f068c41d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (ancien titre, nouveau titre, nouvelle description)
RENAMES = [
    (
        'Spot les différences',
        "Retrouve l'image",
        "Repère l'image demandée parmi plusieurs",
    ),
    (
        'Classe les objets',
        "Trouve l'intrus",
        "Repère l'image qui ne va pas avec les autres",
    ),
]


def upgrade() -> None:
    for old_title, new_title, new_description in RENAMES:
        op.execute(
            sa.text(
                'UPDATE games SET title = :new_title, '
                'description = :new_description WHERE title = :old_title'
            ).bindparams(
                new_title=new_title,
                new_description=new_description,
                old_title=old_title,
            )
        )


def downgrade() -> None:
    restore = [
        (
            "Retrouve l'image",
            'Spot les différences',
            'Trouve les différences entre deux images',
        ),
        (
            "Trouve l'intrus",
            'Classe les objets',
            'Range les objets dans la bonne catégorie',
        ),
    ]
    for current_title, old_title, old_description in restore:
        op.execute(
            sa.text(
                'UPDATE games SET title = :old_title, '
                'description = :old_description WHERE title = :current_title'
            ).bindparams(
                old_title=old_title,
                old_description=old_description,
                current_title=current_title,
            )
        )
