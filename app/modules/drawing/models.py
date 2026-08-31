from sqlalchemy import Column, ForeignKey, Integer, String
from app.database import Base
from app.shared.models import TimestampMixin


class Drawing(Base, TimestampMixin):
    """Création enregistrée par l'enfant (dessin libre ou coloriage).

    Les modèles de coloriage (contours à colorier) sont des assets fournis
    avec l'application mobile — seul le résultat créé par l'enfant est
    persisté ici. `template_key` identifie le modèle utilisé côté app
    (ex: "sun", "house") ou vaut `None` pour un dessin libre.
    """

    __tablename__ = "drawings"

    child_id = Column(
        Integer,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_key = Column(String, nullable=True)
    title = Column(String, nullable=True)
    image_url = Column(String, nullable=False)
