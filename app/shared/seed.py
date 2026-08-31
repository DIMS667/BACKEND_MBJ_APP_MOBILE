import asyncio
import hashlib
import io
import os
import re
import unicodedata
import httpx
from gtts import gTTS
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from app.database import AsyncSessionLocal
from app.config import settings

from app.modules.auth.models import User, RefreshToken                        # noqa
from app.modules.children.models import Child                                 # noqa
from app.modules.communication.models import PictoCategory, Pictogram         # noqa
from app.modules.communication.models import FavoritePicto, SentenceHistory   # noqa
from app.modules.emotions.models import Emotion, CalmingActivity              # noqa
from app.modules.routines.models import Routine, RoutineStep, RoutineSession  # noqa
from app.modules.games.models import GameCategory, Game                       # noqa
from app.modules.games.content_catalog import VERIFIED_IMAGE_IDS              # noqa
from app.modules.stories.models import Story, StoryChoice, StoryPage          # noqa
from app.modules.stories.story_catalog import STORIES_SPRINT_1_DATA           # noqa
from app.modules.audio.models import AudioCategory, AudioFile                 # noqa


SEED_DATA = {
    "Mots essentiels": {
        "color": "#B4A7E5",
        "order": 0,
        "icon_url": "https://static.arasaac.org/pictograms/5441/5441_300.png",
        # Vocabulaire "core" AAC : mots-pivots à haute fréquence qui se
        # combinent avec n'importe quel pictogramme des autres catégories
        # pour construire des phrases (ex: "je veux" + "manger").
        "words": ["je veux", "j'ai", "je suis", "j'aime", "encore", "arrête", "oui", "non"]
    },
    "Besoins": {
        "color": "#FF9AA2",
        "order": 1,
        "icon_url": "https://static.arasaac.org/pictograms/6456/6456_300.png",
        "words": ["manger", "boire", "dormir", "toilettes", "aide", "mal", "chaud", "froid"]
    },
    "Émotions": {
        "color": "#FFB347",
        "order": 2,
        "icon_url": "https://static.arasaac.org/pictograms/35547/35547_300.png",
        "words": ["heureux", "triste", "colère", "peur", "calme", "fatigué", "surpris", "amour"]
    },
    "Activités": {
        "color": "#98FB98",
        "order": 3,
        "icon_url": "https://static.arasaac.org/pictograms/23392/23392_300.png",
        "words": ["jouer", "dessiner", "lire", "musique", "sport", "école", "sortir", "regarder"]
    },
    "Personnes": {
        "color": "#87CEEB",
        "order": 4,
        "icon_url": "https://static.arasaac.org/pictograms/2458/2458_300.png",
        "words": ["maman", "papa", "ami", "médecin", "professeur", "famille", "bébé", "enfant"]
    },
    "Objets": {
        "color": "#DDA0DD",
        "order": 5,
        "icon_url": "https://static.arasaac.org/pictograms/3241/3241_300.png",
        "words": ["ballon", "livre", "eau", "nourriture", "jouet", "voiture", "téléphone", "lit"]
    },
}

EMOTIONS_DATA = [
    {"name": "joie",      "color": "#F7E3B0", "is_positive": True,  "icon_url": "https://static.arasaac.org/pictograms/35547/35547_300.png"},
    {"name": "tristesse", "color": "#C9D8E6", "is_positive": False, "icon_url": "https://static.arasaac.org/pictograms/35545/35545_300.png"},
    {"name": "colère",    "color": "#E5C3BB", "is_positive": False, "icon_url": "https://static.arasaac.org/pictograms/35567/35567_300.png"},
    {"name": "peur",      "color": "#D8CFE6", "is_positive": False, "icon_url": "https://static.arasaac.org/pictograms/35571/35571_300.png"},
    {"name": "fatigue",   "color": "#DCD3CB", "is_positive": False, "icon_url": "https://static.arasaac.org/pictograms/35537/35537_300.png"},
    {"name": "stress",    "color": "#DFCBD9", "is_positive": False, "icon_url": "https://static.arasaac.org/pictograms/35529/35529_300.png"},
    {"name": "calme",     "color": "#C9DFD8", "is_positive": True,  "icon_url": "https://static.arasaac.org/pictograms/31310/31310_300.png"},
]

CALMING_ACTIVITIES_DATA = [
    {
        "name": "Respiration douce",
        "type": "breathing",
        "description": "Inspire doucement, puis souffle lentement.",
        "duration_seconds": 120,
        "icon_url": "https://static.arasaac.org/pictograms/31310/31310_300.png",
        "display_order": 1,
        "is_active": True,
    },
    {
        "name": "Musique apaisante",
        "type": "music",
        "description": "Écoute une mélodie douce à ton rythme.",
        "duration_seconds": 180,
        "icon_url": "https://static.arasaac.org/pictograms/24791/24791_300.png",
        "display_order": 2,
        "is_active": True,
    },
    {
        "name": "Animation relaxante",
        "type": "animation",
        "description": "Regarde le mouvement calme aussi longtemps que tu veux.",
        "duration_seconds": 60,
        "icon_url": "https://static.arasaac.org/pictograms/31310/31310_300.png",
        "display_order": 3,
        "is_active": True,
    },
    {
        "name": "Jeu calme",
        "type": "game",
        "description": "Choisis un jeu doux, sans limite de temps.",
        "duration_seconds": 300,
        "icon_url": "https://static.arasaac.org/pictograms/23392/23392_300.png",
        "display_order": 4,
        "is_active": True,
    },
    {
        "name": "Presser mes mains",
        "type": "sensory",
        "description": "Presse tes mains, puis relâche doucement.",
        "duration_seconds": 60,
        "icon_url": None,
        "display_order": 5,
        "is_active": True,
    },
    {
        "name": "Bouger doucement",
        "type": "movement",
        "description": "Étire ou balance ton corps doucement.",
        "duration_seconds": 90,
        "icon_url": None,
        "display_order": 6,
        "is_active": True,
    },
    {
        "name": "Regarder autour de moi",
        "type": "grounding",
        "description": "Regarde tranquillement les choses autour de toi.",
        "duration_seconds": 60,
        "icon_url": None,
        "display_order": 7,
        "is_active": True,
    },
    {
        "name": "Faire une pause au calme",
        "type": "quiet",
        "description": "Va au calme aussi longtemps que tu veux.",
        "duration_seconds": 180,
        "icon_url": None,
        "display_order": 8,
        "is_active": True,
    },
]

ROUTINES_DATA = [
    {
        "title": "Routine du matin", "type": "morning",
        "icon_url": "https://static.arasaac.org/pictograms/2725/2725_300.png",
        "steps": [
            {"order": 1, "title": "Se réveiller"},
            {"order": 2, "title": "Se laver le visage"},
            {"order": 3, "title": "Se brosser les dents"},
            {"order": 4, "title": "S'habiller"},
            {"order": 5, "title": "Prendre le petit-déjeuner"},
            {"order": 6, "title": "Préparer son sac"},
        ]
    },
    {
        "title": "Routine du soir", "type": "evening",
        "icon_url": "https://static.arasaac.org/pictograms/4877/4877_300.png",
        "steps": [
            {"order": 1, "title": "Ranger ses affaires"},
            {"order": 2, "title": "Se laver"},
            {"order": 3, "title": "Mettre le pyjama"},
            {"order": 4, "title": "Lire une histoire"},
            {"order": 5, "title": "Dormir"},
        ]
    },
    {
        "title": "Routine école", "type": "school",
        "icon_url": "https://static.arasaac.org/pictograms/32446/32446_300.png",
        "steps": [
            {"order": 1, "title": "Arriver en classe"},
            {"order": 2, "title": "Accrocher son manteau"},
            {"order": 3, "title": "S'asseoir"},
            {"order": 4, "title": "Sortir ses affaires"},
            {"order": 5, "title": "Dire bonjour"},
        ]
    },
]

GAMES_DATA = [
    {
        "name": "Mémoire", "description": "Retrouver des paires de cartes identiques",
        "color": "#98FB98", "order": 1,
        "icon_url": "https://static.arasaac.org/pictograms/5362/5362_300.png",
        "games": [
            {"title": "Paires d'animaux",  "description": "Retrouve les paires d'animaux cachées",       "icon_url": "https://static.arasaac.org/pictograms/5362/5362_300.png",   "min_level": 1, "max_level": 5},
            {"title": "Paires d'émotions", "description": "Retrouve les paires de visages expressifs",   "icon_url": "https://static.arasaac.org/pictograms/35547/35547_300.png", "min_level": 1, "max_level": 5},
        ]
    },
    {
        "name": "Concentration", "description": "Améliorer l'attention soutenue",
        "color": "#87CEEB", "order": 2,
        "icon_url": "https://static.arasaac.org/pictograms/6565/6565_300.png",
        "games": [
            {"title": "Trouve l'objet",       "description": "Trouve un objet précis dans une scène",          "icon_url": "https://static.arasaac.org/pictograms/6565/6565_300.png", "min_level": 1, "max_level": 5},
            {"title": "Spot les différences", "description": "Trouve les différences entre deux images",        "icon_url": "https://static.arasaac.org/pictograms/6564/6564_300.png", "min_level": 1, "max_level": 5},
        ]
    },
    {
        "name": "Logique", "description": "Développer le raisonnement",
        "color": "#DDA0DD", "order": 3,
        "icon_url": "https://static.arasaac.org/pictograms/7141/7141_300.png",
        "games": [
            {"title": "Complète la suite", "description": "Complète la suite logique de formes",        "icon_url": "https://static.arasaac.org/pictograms/7141/7141_300.png", "min_level": 1, "max_level": 5},
            {"title": "Classe les objets", "description": "Range les objets dans la bonne catégorie",   "icon_url": "https://static.arasaac.org/pictograms/9813/9813_300.png", "min_level": 1, "max_level": 5},
            {"title": "Séquence routine", "description": "Remets les étapes du quotidien dans le bon ordre", "icon_url": "https://static.arasaac.org/pictograms/2725/2725_300.png", "min_level": 1, "max_level": 5},
        ]
    },
    {
        "name": "Reconnaissance", "description": "Identifier couleurs, sons, animaux",
        "color": "#FFB347", "order": 4,
        "icon_url": "https://static.arasaac.org/pictograms/2300/2300_300.png",
        "games": [
            {"title": "Reconnais l'animal",  "description": "Associe le son à l'animal correspondant", "icon_url": "https://static.arasaac.org/pictograms/5362/5362_300.png", "min_level": 1, "max_level": 5},
            {"title": "Reconnais la couleur","description": "Identifie les couleurs des objets",        "icon_url": "https://static.arasaac.org/pictograms/2300/2300_300.png", "min_level": 1, "max_level": 5},
        ]
    },
    {
        "name": "Association", "description": "Créer des liens entre concepts",
        "color": "#FF9AA2", "order": 5,
        "icon_url": "https://static.arasaac.org/pictograms/35547/35547_300.png",
        "games": [
            {"title": "Émotion et situation", "description": "Associe une émotion à une situation du quotidien", "icon_url": "https://static.arasaac.org/pictograms/35547/35547_300.png", "min_level": 1, "max_level": 5},
            {"title": "Objet et utilisation", "description": "Associe chaque objet à son utilisation",           "icon_url": "https://static.arasaac.org/pictograms/9813/9813_300.png",  "min_level": 1, "max_level": 5},
        ]
    },
]

AUDIO_DATA = [
    {
        "name": "calming", "description": "Sons apaisants pour la régulation émotionnelle",
        "icon_url": "https://static.arasaac.org/pictograms/31310/31310_300.png",
        "files": [
            {"title": "Respiration guidée",  "text": "Inspire doucement... et expire doucement...",           "filename": "calming_respiration.mp3"},
            {"title": "Encouragement doux",  "text": "Tu fais du très bon travail. Continue ainsi.",          "filename": "calming_encouragement.mp3"},
            {"title": "Relaxation douce",    "text": "Ferme les yeux. Tu es en sécurité. Tout va bien.",      "filename": "calming_relaxation.mp3"},
        ]
    },
    {
        "name": "feedback", "description": "Sons de retour positif après les exercices",
        "icon_url": "https://static.arasaac.org/pictograms/35547/35547_300.png",
        "files": [
            {"title": "Bravo",          "text": "Bravo ! Tu as très bien fait !",                             "filename": "feedback_bravo.mp3"},
            {"title": "Excellent",      "text": "Excellent travail ! Tu es fantastique !",                    "filename": "feedback_excellent.mp3"},
            {"title": "Super",          "text": "Super ! Continue comme ça !",                                "filename": "feedback_super.mp3"},
            {"title": "Félicitations",  "text": "Félicitations ! Tu as terminé ! Je suis très fier de toi.", "filename": "feedback_felicitations.mp3"},
        ]
    },
    {
        "name": "narration", "description": "Narrations des histoires sociales",
        "icon_url": "https://static.arasaac.org/pictograms/7141/7141_300.png",
        "files": [
            {"title": "Introduction histoires", "text": "Bienvenue dans les histoires de la Maison Bleue.", "filename": "narration_intro.mp3"},
            {"title": "Fin d'histoire",         "text": "L'histoire est terminée. Tu as très bien écouté !", "filename": "narration_fin.mp3"},
        ]
    },
    {
        "name": "tts", "description": "Synthèse vocale générée pour les pictogrammes",
        "icon_url": "https://static.arasaac.org/pictograms/6563/6563_300.png",
        "files": []
    },
]


ARASAAC_SEARCH_URL = "https://api.arasaac.org/v1/pictograms/fr/search/{word}"
ARASAAC_IMAGE_URL  = "https://static.arasaac.org/pictograms/{id}/{id}_300.png"

# fetch_picto_id() prend par défaut le 1er résultat de recherche ARASAAC,
# ce qui n'est pas toujours le plus pertinent sémantiquement (ex: "froid"
# retournait un verre d'eau glacée plutôt qu'une personne qui grelotte).
# Overrides vérifiés manuellement mot par mot au fur et à mesure.
MANUAL_PICTO_OVERRIDES = {
    "froid": 35583,  # personne qui grelotte ("avoir froid"), pas un verre glacé
    # Mots-pivots (catégorie "Mots essentiels") : la recherche automatique
    # ARASAAC indexe des lemmes ("vouloir", "aimer"...), pas les formes
    # conjuguées affichées à l'enfant — ID vérifié manuellement + libellé
    # forcé à la forme exacte recherchée (voir fetch_picto_id ci-dessous).
    "je veux": 5441,   # "vouloir" — mot-clé ARASAAC inclut déjà "je veux"
    "j'ai": 32761,     # "avoir, tenir, posséder"
    "je suis": 6632,   # "je, me, moi" — silhouette qui se désigne
    "j'aime": 37826,   # "j'aime ça, aimer, apprécier"
    "encore": 37163,   # "encore, une autre fois, à nouveau"
    "arrête": 7196,    # "arrêter, stopper"
    "oui": 5584,       # "oui, ok"
    "non": 5526,       # "non"
}


async def fetch_picto_id(word: str) -> tuple:
    if word in MANUAL_PICTO_OVERRIDES:
        return MANUAL_PICTO_OVERRIDES[word], word
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(ARASAAC_SEARCH_URL.format(word=word))
            if resp.status_code == 200:
                results = resp.json()
                if results:
                    first = results[0]
                    return first["_id"], first.get("keywords", [{}])[0].get("keyword", word)
        except Exception as e:
            print(f"      ⚠️  Erreur ARASAAC pour '{word}': {e}")
    return None, word


def _slugify(word: str) -> str:
    """ASCII-fie un mot pour un nom de fichier sûr à servir en HTTP.

    Vérifié en prod : bébé_*.png, médecin_*.png, colère_*.png (et leurs
    équivalents audio) renvoient 404 alors que le fichier est valide sur
    disque et que chaud_*.png (sans accent) fonctionne — un maillon de la
    chaîne serveur (filesystem Linux du mutualisé, ou le proxy de cache
    devant) ne gère pas ces noms correctement. On évite le problème à la
    source plutôt que d'en chercher la cause exacte sur un serveur qu'on
    ne contrôle pas.
    """
    normalized = unicodedata.normalize("NFKD", word)
    ascii_word = normalized.encode("ascii", "ignore").decode("ascii")
    # Apostrophes ("j'ai", "j'aime") : même prudence que pour les accents
    # ci-dessus, on évite de les laisser dans un nom de fichier servi en HTTP.
    return ascii_word.replace("'", "")


def _legacy_image_path(word: str, arasaac_id: int) -> tuple:
    images_dir = os.path.join(settings.STORAGE_PATH, "pictos")
    filename = f"{word.replace(' ', '_')}_{arasaac_id}.png"
    return os.path.join(images_dir, filename), f"/storage/pictos/{filename}"


def _image_path(word: str, arasaac_id: int) -> tuple:
    images_dir = os.path.join(settings.STORAGE_PATH, "pictos")
    os.makedirs(images_dir, exist_ok=True)
    filename = f"{_slugify(word).replace(' ', '_')}_{arasaac_id}.png"
    return os.path.join(images_dir, filename), f"/storage/pictos/{filename}"


def _audio_path(word: str, text: str) -> tuple:
    """Le nom de fichier inclut un hash du texte réellement synthétisé.

    Sans ça, `_ensure_audio` ne régénère jamais un fichier déjà présent —
    si le texte source change (ex: le texte d'une page d'histoire est
    corrigé dans story_catalog.py) sans que le nom de fichier change,
    l'audio reste bloqué sur l'ancienne version indéfiniment : le texte
    affiché (toujours à jour, recréé à chaque seed) diverge alors de la
    voix jouée. Le hash invalide le cache automatiquement dès que `text`
    change, sans coût de régénération quand rien n'a changé.
    """
    audio_dir = os.path.join(settings.STORAGE_PATH, "audio", "pictos")
    os.makedirs(audio_dir, exist_ok=True)
    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    filename = f"{_slugify(word).replace(' ', '_')}_{text_hash}.mp3"
    return os.path.join(audio_dir, filename), f"/storage/audio/pictos/{filename}"


def _reencode_png_bytes(raw: bytes) -> bytes:
    """Ré-encode des octets PNG en RGBA à IDAT unique.

    Certains exports ARASAAC sont des PNG indexés (mode palette) dont les
    données compressées sont réparties sur plusieurs chunks IDAT — un
    format valide selon la spec PNG, mais que le décodeur natif Android
    (`ImageDecoder`, utilisé par le rendu Impeller de Flutter) refuse avec
    `DecodeException: unimplemented — Input contained an error`. Pillow
    réencode toujours en un seul IDAT, ce qui contourne le problème.
    """
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _renormalize_existing_png(filepath: str) -> None:
    """Ré-encode en place un PNG déjà présent sur disque — nécessaire pour
    les fichiers téléchargés par un seed précédent avant le fix du format
    (voir `_reencode_png_bytes`) : sans ça, le court-circuit "déjà présent"
    laisserait le fichier cassé sur disque indéfiniment."""
    try:
        with open(filepath, "rb") as f:
            raw = f.read()
        fixed = _reencode_png_bytes(raw)
        if fixed != raw:
            with open(filepath, "wb") as f:
                f.write(fixed)
    except Exception as e:
        print(f"      ⚠️  Ré-encodage du fichier existant échoué ({filepath}): {e}")


async def _ensure_image(word: str, arasaac_id: int) -> str:
    filepath, local_url = _image_path(word, arasaac_id)
    if os.path.exists(filepath):
        _renormalize_existing_png(filepath)
        print(f"      📁 Image déjà présente (ré-encodée si besoin) : {os.path.basename(filepath)}")
        return local_url
    url = ARASAAC_IMAGE_URL.format(id=arasaac_id)
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(_reencode_png_bytes(resp.content))
                print(f"      ⬇️  Image téléchargée : {os.path.basename(filepath)}")
                return local_url
        except Exception as e:
            print(f"      ⚠️  Téléchargement échoué pour '{word}': {e}")
    print(f"      🔗 Fallback URL distante pour '{word}'")
    return url


_ARASAAC_ID_RE = re.compile(r"/pictograms/(\d+)/")


def _arasaac_local_path(arasaac_id: int) -> tuple:
    images_dir = os.path.join(settings.STORAGE_PATH, "pictos", "shared")
    os.makedirs(images_dir, exist_ok=True)
    filename = f"arasaac_{arasaac_id}.png"
    return (
        os.path.join(images_dir, filename),
        f"/storage/pictos/shared/{filename}",
    )


async def _ensure_arasaac_by_id(arasaac_id: int) -> str:
    filepath, local_url = _arasaac_local_path(arasaac_id)
    if os.path.exists(filepath):
        _renormalize_existing_png(filepath)
        return local_url
    url = ARASAAC_IMAGE_URL.format(id=arasaac_id)
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(_reencode_png_bytes(resp.content))
                print(f"      ⬇️  Image ARASAAC {arasaac_id} téléchargée et ré-encodée")
                return local_url
        except Exception as e:
            print(f"      ⚠️  Téléchargement/ré-encodage échoué pour l'ID {arasaac_id}: {e}")
    print(f"      🔗 Fallback URL distante pour l'ID {arasaac_id}")
    return url


async def _localize_arasaac_url(url: str | None) -> str | None:
    """Si `url` pointe vers static.arasaac.org, télécharge + ré-encode en
    local (voir `_reencode_png_bytes`) et retourne le chemin local ;
    sinon retourne `url` inchangé (déjà local, vide, ou autre origine)."""
    if not url:
        return url
    match = _ARASAAC_ID_RE.search(url)
    if not match:
        return url
    return await _ensure_arasaac_by_id(int(match.group(1)))


def _ensure_audio(label: str, word: str) -> str:
    filepath, local_url = _audio_path(word, label)
    if os.path.exists(filepath):
        print(f"      📁 Audio déjà présent : {os.path.basename(filepath)}")
        return local_url
    try:
        tts = gTTS(text=label, lang="fr", slow=False)
        tts.save(filepath)
        print(f"      🔊 Audio généré : {os.path.basename(filepath)}")
        return local_url
    except Exception as e:
        print(f"      ⚠️  Génération audio échouée pour '{label}': {e}")
        return None


# ─────────────────────────────────────────────────────────────────
# SEED COMMUNICATION — CORRIGÉ
# Fix : vérification par image_url au lieu de label
# pour éviter les doublons quand ARASAAC retourne un label
# différent du mot recherché (ex: "aide" → "appui")
# ─────────────────────────────────────────────────────────────────

async def seed_communication(db: AsyncSession) -> None:
    print("\n🌱 Seed Communication...\n")

    for cat_name, cat_data in SEED_DATA.items():

        result = await db.execute(
            select(PictoCategory).where(PictoCategory.name == cat_name)
        )
        category = result.scalar_one_or_none()
        icon_url = await _localize_arasaac_url(cat_data.get("icon_url"))

        if not category:
            category = PictoCategory(
                name=cat_name,
                color=cat_data["color"],
                order=cat_data["order"],
                icon_url=icon_url,
            )
            db.add(category)
            await db.flush()
            print(f"✅ Catégorie créée : {cat_name}")
        else:
            category.color = cat_data["color"]
            category.order = cat_data["order"]
            category.icon_url = icon_url
            print(f"🔄 Catégorie mise à jour : {cat_name}")

        for word in cat_data["words"]:
            print(f"   🔍 Traitement : {word}")

            # 1. Récupérer l'ID ARASAAC en premier
            arasaac_id, label = await fetch_picto_id(word)

            # 2. Vérifier l'existence par image_url (fiable même si label diffère)
            existing_picto = None
            if arasaac_id:
                _, local_img_url = _image_path(word, arasaac_id)
                result = await db.execute(
                    select(Pictogram).where(
                        Pictogram.image_url == local_img_url,
                        Pictogram.category_id == category.id,
                    )
                )
                existing_picto = result.scalar_one_or_none()
                if existing_picto is None:
                    # Fallback : ancien nom de fichier avant ASCII-fication
                    # (voir _slugify) — migre l'enregistrement au lieu d'en
                    # créer un doublon.
                    _, legacy_img_url = _legacy_image_path(word, arasaac_id)
                    if legacy_img_url != local_img_url:
                        result = await db.execute(
                            select(Pictogram).where(
                                Pictogram.image_url == legacy_img_url,
                                Pictogram.category_id == category.id,
                            )
                        )
                        existing_picto = result.scalar_one_or_none()
                if existing_picto is None:
                    # Fallback : même mot mais ID ARASAAC différent de celui
                    # stocké (ex: MANUAL_PICTO_OVERRIDES change l'ID choisi
                    # pour un mot déjà seedé) — migre par préfixe de fichier
                    # plutôt que de créer un doublon.
                    prefix = f"/storage/pictos/{_slugify(word).replace(' ', '_')}_"
                    result = await db.execute(
                        select(Pictogram).where(
                            Pictogram.image_url.like(f"{prefix}%"),
                            Pictogram.category_id == category.id,
                        )
                    )
                    existing_picto = result.scalars().first()
            else:
                # Fallback : vérifier par label si pas d'ID ARASAAC
                result = await db.execute(
                    select(Pictogram).where(
                        Pictogram.label == word,
                        Pictogram.category_id == category.id,
                    )
                )
                existing_picto = result.scalar_one_or_none()

            # 3. Télécharger l'image et générer l'audio — même si le picto
            # existe déjà en base : le fichier sur disque, lui, peut dater
            # d'un seed antérieur au fix du format PNG (voir _ensure_image).
            if arasaac_id:
                image_url = await _ensure_image(word, arasaac_id)
            else:
                image_url = f"https://placehold.co/300x300?text={word}"
                label = word

            audio_url = _ensure_audio(label, word)

            if existing_picto:
                existing_picto.label = label
                existing_picto.image_url = image_url
                existing_picto.audio_url = audio_url
                print(f"   🔄 Picto mis à jour : {word} → {label}")
                continue

            picto = Pictogram(
                category_id=category.id,
                label=label,
                image_url=image_url,
                audio_url=audio_url,
                is_default=True,
            )
            db.add(picto)
            print(f"   🖼️  Picto inséré : {label}")

        await db.commit()
        print(f"   💾 '{cat_name}' sauvegardé !\n")

    print("🎉 Seed Communication terminé !\n")


async def seed_emotions(db: AsyncSession) -> None:
    print("\n🌱 Seed Emotions...\n")
    for emotion_data in EMOTIONS_DATA:
        emotion_data = {
            **emotion_data,
            "icon_url": await _localize_arasaac_url(emotion_data.get("icon_url")),
        }
        result = await db.execute(select(Emotion).where(Emotion.name == emotion_data["name"]))
        emotion = result.scalar_one_or_none()
        if emotion is None:
            db.add(Emotion(**emotion_data))
            print(f"   😊 Émotion créée : {emotion_data['name']}")
            continue
        for field, value in emotion_data.items():
            setattr(emotion, field, value)
        print(f"   🔄 Émotion mise à jour : {emotion_data['name']}")
    for activity_data in CALMING_ACTIVITIES_DATA:
        activity_data = {
            **activity_data,
            "icon_url": await _localize_arasaac_url(activity_data.get("icon_url")),
        }
        result = await db.execute(select(CalmingActivity).where(CalmingActivity.name == activity_data["name"]))
        activity = result.scalar_one_or_none()
        if activity is None:
            db.add(CalmingActivity(**activity_data))
            print(f"   🧘 Activité créée : {activity_data['name']}")
            continue
        for field, value in activity_data.items():
            setattr(activity, field, value)
        print(f"   🔄 Activité mise à jour : {activity_data['name']}")
    await db.commit()
    print("\n🎉 Seed Emotions terminé !\n")


async def seed_routines(db: AsyncSession) -> None:
    print("\n🌱 Seed Routines...\n")
    result = await db.execute(select(Child))
    children = result.scalars().all()
    if not children:
        print("   ⚠️  Aucun enfant en base — seed routines ignoré.")
        return
    for child in children:
        print(f"   👦 Routines pour : {child.first_name} (id={child.id})")
        for routine_data in ROUTINES_DATA:
            icon_url = await _localize_arasaac_url(routine_data["icon_url"])
            result = await db.execute(
                select(Routine).where(Routine.child_id == child.id, Routine.type == routine_data["type"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.icon_url = icon_url
                print(f"      🔄 Routine mise à jour : {routine_data['title']}")
                continue
            routine = Routine(
                child_id=child.id,
                title=routine_data["title"],
                type=routine_data["type"],
                icon_url=icon_url,
                is_default=True,
            )
            db.add(routine)
            await db.flush()
            for step_data in routine_data["steps"]:
                db.add(RoutineStep(
                    routine_id=routine.id,
                    order=step_data["order"],
                    title=step_data["title"],
                    is_default=True,
                ))
            print(f"      📋 Routine créée : {routine_data['title']}")
    await db.commit()
    print("\n🎉 Seed Routines terminé !\n")


async def seed_games(db: AsyncSession) -> None:
    print("\n🌱 Seed Games...\n")
    for cat_data in GAMES_DATA:
        result = await db.execute(select(GameCategory).where(GameCategory.name == cat_data["name"]))
        category = result.scalar_one_or_none()
        cat_icon_url = await _localize_arasaac_url(cat_data["icon_url"])
        if not category:
            category = GameCategory(name=cat_data["name"], description=cat_data["description"], color=cat_data["color"], order=cat_data["order"], icon_url=cat_icon_url)
            db.add(category)
            await db.flush()
            print(f"✅ Catégorie jeu créée : {cat_data['name']}")
        else:
            category.description = cat_data["description"]
            category.color = cat_data["color"]
            category.order = cat_data["order"]
            category.icon_url = cat_icon_url
            print(f"🔄 Catégorie jeu mise à jour : {cat_data['name']}")
        for game_data in cat_data["games"]:
            game_icon_url = await _localize_arasaac_url(game_data["icon_url"])
            existing = await db.execute(select(Game).where(Game.title == game_data["title"], Game.category_id == category.id))
            game = existing.scalar_one_or_none()
            if game is None:
                db.add(Game(category_id=category.id, title=game_data["title"], description=game_data["description"], icon_url=game_icon_url, min_level=game_data["min_level"], max_level=game_data["max_level"], is_offline_available=True))
                print(f"   🎮 Jeu créé : {game_data['title']}")
                continue
            game.description = game_data["description"]
            game.icon_url = game_icon_url
            game.min_level = game_data["min_level"]
            game.max_level = game_data["max_level"]
            print(f"   🔄 Jeu mis à jour : {game_data['title']}")
    await db.commit()
    print("\n🎉 Seed Games terminé !\n")


async def seed_stories(db: AsyncSession) -> None:
    print("\n🌱 Seed Stories...\n")
    for story_data in STORIES_SPRINT_1_DATA:
        result = await db.execute(select(Story).where(Story.title == story_data["title"]))
        story = result.scalar_one_or_none()
        if story is None:
            story = Story()
            db.add(story)
        story.title = story_data["title"]
        story.description = story_data["description"]
        story.category = story_data["category"]
        story.cover_url = await _localize_arasaac_url(story_data["cover_url"])
        story.total_pages = len(story_data["pages"])
        story.is_offline_available = True
        story.is_custom = False
        story.owner_id = None
        story.child_id = None
        story.client_uuid = None
        await db.flush()
        await db.execute(delete(StoryPage).where(StoryPage.story_id == story.id))
        await db.flush()
        for page_data in story_data["pages"]:
            audio_url = _ensure_audio(page_data["text"], f"story_{story.id}_page_{page_data['page_number']}")
            page = StoryPage(
                story_id=story.id,
                page_number=page_data["page_number"],
                text=page_data["text"],
                image_url=await _localize_arasaac_url(page_data.get("image_url")),
                pictogram_url=await _localize_arasaac_url(page_data.get("pictogram_url")),
                audio_url=audio_url,
                animation_type=page_data.get("animation_type", "fade"),
                next_page_number=page_data.get("next_page_number"),
            )
            db.add(page)
            await db.flush()
            for choice_data in page_data.get("choices", []):
                db.add(
                    StoryChoice(
                        page_id=page.id,
                        label=choice_data["label"],
                        pictogram_url=await _localize_arasaac_url(choice_data.get("pictogram_url")),
                        next_page_number=choice_data["next_page_number"],
                        sort_order=choice_data.get("sort_order", 0),
                    )
                )
        print(f"   📖 Histoire synchronisée : {story_data['title']} ({len(story_data['pages'])} pages)")
    await db.commit()
    print("\n🎉 Seed Stories terminé !\n")


async def seed_audio(db: AsyncSession) -> None:
    print("\n🌱 Seed Audio...\n")
    for cat_data in AUDIO_DATA:
        result = await db.execute(select(AudioCategory).where(AudioCategory.name == cat_data["name"]))
        category = result.scalar_one_or_none()
        audio_cat_icon_url = await _localize_arasaac_url(cat_data["icon_url"])
        if not category:
            category = AudioCategory(name=cat_data["name"], description=cat_data["description"], icon_url=audio_cat_icon_url)
            db.add(category)
            await db.flush()
            print(f"✅ Catégorie audio créée : {cat_data['name']}")
        else:
            category.description = cat_data["description"]
            category.icon_url = audio_cat_icon_url
            print(f"🔄 Catégorie audio mise à jour : {cat_data['name']}")
        for file_data in cat_data["files"]:
            existing = await db.execute(select(AudioFile).where(AudioFile.title == file_data["title"], AudioFile.category_id == category.id))
            if existing.scalar_one_or_none():
                print(f"   ⏭️  Audio existant : {file_data['title']}")
                continue
            audio_url = _ensure_audio(file_data["text"], file_data["filename"].replace(".mp3", ""))
            db.add(AudioFile(category_id=category.id, title=file_data["title"], file_url=audio_url or f"/storage/audio/pictos/{file_data['filename']}", language="fr", is_local=True))
            print(f"   🔊 Audio créé : {file_data['title']}")
    await db.commit()
    print("\n🎉 Seed Audio terminé !\n")


async def seed_game_content_images() -> None:
    """Pré-télécharge et ré-encode localement les images ARASAAC utilisées
    par le contenu généré à la volée des jeux (voir content_catalog.py —
    ces URLs sont construites par requête, pas stockées en base, donc le
    cache doit exister sur disque AVANT que l'app ne les référence)."""
    print("\n🌱 Seed Game Content Images...\n")
    unique_ids = sorted(set(VERIFIED_IMAGE_IDS.values()))
    for arasaac_id in unique_ids:
        await _ensure_arasaac_by_id(arasaac_id)
    print(f"\n🎉 Seed Game Content Images terminé ({len(unique_ids)} images) !\n")


async def main():
    async with AsyncSessionLocal() as db:
        await seed_communication(db)
        await seed_emotions(db)
        await seed_routines(db)
        await seed_games(db)
        await seed_stories(db)
        await seed_audio(db)
    await seed_game_content_images()


if __name__ == "__main__":
    asyncio.run(main())
