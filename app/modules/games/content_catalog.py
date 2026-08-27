import random
from datetime import datetime, timezone
from typing import Any

from .models import Game


CONTENT_VERSION = 3
MAX_CHALLENGE_RANK = 15
CHALLENGES_PER_LEVEL = 3


# IDs validated against the official ARASAAC French catalog. Legacy IDs are
# deliberately ignored: an unverified asset falls back to its emoji rather
# than showing a misleading pictogram.
VERIFIED_IMAGE_IDS = {
    "animal_dog": 7202,
    "animal_cat": 7114,
    "animal_rabbit": 2351,
    "animal_frog": 28473,
    "animal_lion": 25187,
    "animal_bear": 2488,
    "animal_turtle": 26503,
    "animal_fish": 2520,
    "animal_bird": 2490,
    "animal_butterfly": 26200,
    "food_apple": 2462,
    "food_banana": 2530,
    "food_bread": 2494,
    "food_water": 32464,
    "food_soup": 2573,
    "food_yogurt": 2618,
    "food_carrot": 2619,
    "food_cookie": 8312,
    "food_orange": 2888,
    "food_strawberry": 2400,
    "food_pear": 2561,
    "food_milk": 2445,
    "school_bag": 2475,
    "school_book": 25191,
    "school_pencil": 2440,
    "school_chair": 3155,
    "school_table": 3129,
    "school_teacher": 6556,
    "school_recess": 6204,
    "school_bus": 2263,
    "school_notebook": 2359,
    "school_eraser": 2409,
    "school_scissors": 2591,
    "school_ruler": 2815,
    "home_house": 6964,
    "home_bed": 25900,
    "home_bath": 2272,
    "home_toothbrush": 2694,
    "home_toy": 9813,
    "home_pajamas": 2522,
    "home_sofa": 25479,
    "home_door": 3244,
    "emotion_happy": 35547,
    "emotion_sad": 35545,
    "emotion_angry": 35539,
    "emotion_scared": 10261,
    "emotion_tired": 35537,
    "emotion_calm": 31310,
    "emotion_proud": 31408,
    "emotion_worried": 30391,
    "emotion_surprised": 35529,
    "emotion_disgusted": 30964,
    "action_eat": 6456,
    "action_drink": 6061,
    "action_wash": 34826,
    "action_sleep": 6479,
    "action_play": 23392,
    "action_read": 7141,
    "action_wait": 36914,
    "action_help": 32648,
    "object_toothbrush": 2694,
    "use_brush_teeth": 2326,
    "object_book": 25191,
    "use_read": 7141,
    "object_pencil": 2440,
    "use_draw": 8088,
    "use_eat": 6456,
    "object_bag": 2475,
    "object_bed": 25900,
    "use_sleep": 6479,
    "use_listen": 6572,
    "need_help": 32648,
    "need_breathe": 2486,
    "need_hug": 27407,
    "need_safe": 31310,
    "need_share": 38900,
    "routine_wake": 8989,
    "routine_wash": 34826,
    "routine_dress": 6627,
    "routine_breakfast": 4626,
    "routine_bag": 2475,
    "routine_arrive": 16807,
    "routine_coat": 2242,
    "routine_hello": 6944,
    "routine_sit": 6611,
    "routine_work": 6624,
    "routine_tidy": 2872,
    "routine_bath": 6058,
    "routine_pajamas": 2522,
    "routine_story": 25191,
    "routine_sleep": 6479,
    "routine_brush_teeth": 2326,
    "routine_recess": 6204,
    "routine_listen": 6572,
}


def _asset(
    key: str,
    label: str,
    emoji: str,
    category: str,
    image_id: int | None = None,
) -> dict[str, Any]:
    verified_image_id = VERIFIED_IMAGE_IDS.get(key)
    return {
        "id": key,
        "label": label,
        "emoji": emoji,
        "category": category,
        # Chemin local pré-rempli par `seed_game_content_images()`
        # (app/shared/seed.py) — jamais l'URL ARASAAC brute : certains
        # exports ARASAAC sont des PNG multi-IDAT que le décodeur natif
        # Android (Impeller) refuse de décoder. Si le fichier n'a encore
        # jamais été seedé, l'app affiche l'emoji de secours (voir
        # GameAssetView) plutôt qu'une image cassée.
        "image_url": (
            f"/storage/pictos/shared/arasaac_{verified_image_id}.png"
            if verified_image_id
            else None
        ),
    }


ANIMALS = [
    _asset("animal_dog", "Chien", "🐶", "animaux", 2518),
    _asset("animal_cat", "Chat", "🐱", "animaux", 2467),
    _asset("animal_rabbit", "Lapin", "🐰", "animaux", 2634),
    _asset("animal_frog", "Grenouille", "🐸", "animaux", 2450),
    _asset("animal_lion", "Lion", "🦁", "animaux", 2576),
    _asset("animal_bear", "Ours", "🐻", "animaux", 2602),
    _asset("animal_turtle", "Tortue", "🐢", "animaux", 2784),
    _asset("animal_fish", "Poisson", "🐟", "animaux", 2633),
    _asset("animal_bird", "Oiseau", "🐦", "animaux", 2506),
    _asset("animal_butterfly", "Papillon", "🦋", "animaux", 2615),
]

FOOD = [
    _asset("food_apple", "Pomme", "🍎", "nourriture", 3062),
    _asset("food_banana", "Banane", "🍌", "nourriture", 2404),
    _asset("food_bread", "Pain", "🍞", "nourriture", 2607),
    _asset("food_water", "Eau", "🥤", "nourriture", 5582),
    _asset("food_soup", "Soupe", "🥣", "nourriture", 2772),
    _asset("food_yogurt", "Yaourt", "🥛", "nourriture", 2921),
    _asset("food_carrot", "Carotte", "🥕", "nourriture", 2434),
    _asset("food_cookie", "Biscuit", "🍪", "nourriture", 2409),
]

FOOD.extend(
    [
        _asset("food_orange", "Orange", "🍊", "nourriture", 2888),
        _asset("food_strawberry", "Fraise", "🍓", "nourriture", 2400),
        _asset("food_pear", "Poire", "🍐", "nourriture", 2561),
        _asset("food_milk", "Lait", "🥛", "nourriture", 2445),
    ]
)


SCHOOL = [
    _asset("school_bag", "Sac", "🎒", "école", 2754),
    _asset("school_book", "Livre", "📘", "école", 2577),
    _asset("school_pencil", "Crayon", "✏️", "école", 2674),
    _asset("school_chair", "Chaise", "🪑", "école", 2436),
    _asset("school_table", "Table", "🧩", "école", 2779),
    _asset("school_teacher", "Maître", "👩‍🏫", "école", 2914),
    _asset("school_recess", "Récréation", "🛝", "école", 2684),
    _asset("school_bus", "Bus", "🚌", "école", 2423),
]

SCHOOL.extend(
    [
        _asset("school_notebook", "Cahier", "📓", "école", 2359),
        _asset("school_eraser", "Gomme", "🧽", "école", 2409),
        _asset("school_scissors", "Ciseaux", "✂️", "école", 2591),
        _asset("school_ruler", "Règle", "📏", "école", 2815),
    ]
)


HOME = [
    _asset("home_house", "Maison", "🏠", "maison", 2523),
    _asset("home_bed", "Lit", "🛏️", "maison", 2575),
    _asset("home_bath", "Bain", "🛁", "maison", 2395),
    _asset("home_toothbrush", "Brosse à dents", "🪥", "maison", 2407),
    _asset("home_toy", "Jouet", "🧸", "maison", 2780),
    _asset("home_pajamas", "Pyjama", "🌙", "maison", 2640),
    _asset("home_sofa", "Canapé", "🛋️", "maison", 2429),
    _asset("home_door", "Porte", "🚪", "maison", 2678),
]

EMOTIONS = [
    _asset("emotion_happy", "Content", "😊", "émotions", 2720),
    _asset("emotion_sad", "Triste", "😢", "émotions", 2907),
    _asset("emotion_angry", "Fâché", "😠", "émotions", 2961),
    _asset("emotion_scared", "Peur", "😨", "émotions", 2871),
    _asset("emotion_tired", "Fatigué", "😴", "émotions", 2552),
    _asset("emotion_calm", "Calme", "😌", "émotions", 3114),
    _asset("emotion_proud", "Fier", "🤩", "émotions", 2722),
    _asset("emotion_worried", "Inquiet", "😟", "émotions", 3004),
    _asset("emotion_surprised", "Surpris", "😮", "émotions", 35529),
    _asset("emotion_disgusted", "Dégoûté", "🤢", "émotions", 30964),
]

ACTIONS = [
    _asset("action_eat", "Manger", "🍽️", "actions", 2555),
    _asset("action_drink", "Boire", "🥤", "actions", 5582),
    _asset("action_wash", "Se laver", "🚿", "actions", 2804),
    _asset("action_sleep", "Dormir", "🛏️", "actions", 2392),
    _asset("action_play", "Jouer", "🧸", "actions", 2780),
    _asset("action_read", "Lire", "📖", "actions", 2577),
    _asset("action_wait", "Attendre", "⏳", "actions", 3029),
    _asset("action_help", "Aider", "🤝", "actions", 2954),
]

COLORS = [
    _asset("color_red", "Rouge", "🔴", "couleurs"),
    _asset("color_blue", "Bleu", "🔵", "couleurs"),
    _asset("color_yellow", "Jaune", "🟡", "couleurs"),
    _asset("color_green", "Vert", "🟢", "couleurs"),
    _asset("color_orange", "Orange", "🟠", "couleurs"),
    _asset("color_purple", "Violet", "🟣", "couleurs"),
    _asset("color_black", "Noir", "⚫", "couleurs"),
    _asset("color_white", "Blanc", "⚪", "couleurs"),
    _asset("color_brown", "Marron", "🟤", "couleurs"),
    _asset("color_pink", "Rose", "🩷", "couleurs"),
]

OBJECT_USES = [
    (_asset("object_toothbrush", "Brosse à dents", "🪥", "objets", 2407), _asset("use_brush_teeth", "Se laver les dents", "😁", "usages", 2804)),
    (_asset("object_book", "Livre", "📚", "objets", 2577), _asset("use_read", "Lire", "👀", "usages", 2577)),
    (_asset("object_pencil", "Crayon", "✏️", "objets", 2674), _asset("use_draw", "Dessiner", "🎨", "usages", 2492)),
    (_asset("object_spoon", "Cuillère", "🥄", "objets", 2769), _asset("use_eat", "Manger", "🍽️", "usages", 2555)),
    (_asset("object_umbrella", "Parapluie", "☂️", "objets", 2831), _asset("use_rain", "Quand il pleut", "🌧️", "usages", 2816)),
    (_asset("object_bag", "Sac", "🎒", "objets", 2754), _asset("use_school", "Aller à l’école", "🏫", "usages", 2465)),
    (_asset("object_bed", "Lit", "🛏️", "objets", 2575), _asset("use_sleep", "Dormir", "😴", "usages", 2392)),
    (_asset("object_headphones", "Casque", "🎧", "objets", 2501), _asset("use_listen", "Écouter doucement", "🎵", "usages", 2600)),
]

EMOTION_NEEDS = [
    (_asset("emotion_tired", "Fatigué", "😴", "émotions", 2552), _asset("need_rest", "Se reposer", "🛏️", "besoins", 2392)),
    (_asset("emotion_worried", "Inquiet", "😟", "émotions", 3004), _asset("need_help", "Demander de l’aide", "🤝", "besoins", 2954)),
    (_asset("emotion_angry", "Fâché", "😠", "émotions", 2961), _asset("need_breathe", "Respirer", "🌬️", "besoins", 3114)),
    (_asset("emotion_sad", "Triste", "😢", "émotions", 2907), _asset("need_hug", "Câlin", "🤗", "besoins", 2442)),
    (_asset("emotion_scared", "Peur", "😨", "émotions", 2871), _asset("need_safe", "Aller au calme", "🏡", "besoins", 2523)),
    (_asset("emotion_happy", "Content", "😊", "émotions", 2720), _asset("need_share", "Partager", "🙂", "besoins", 2748)),
]

ROUTINES = [
    {
        "theme": "Le matin",
        "steps": [
            _asset("routine_wake", "Réveil", "⏰", "routine", 3029),
            _asset("routine_wash", "Se laver", "🚿", "routine", 2804),
            _asset("routine_dress", "S’habiller", "👕", "routine", 2498),
            _asset("routine_breakfast", "Déjeuner", "🥣", "routine", 2555),
            _asset("routine_bag", "Prendre le sac", "🎒", "routine", 2754),
        ],
    },
    {
        "theme": "A l’école",
        "steps": [
            _asset("routine_arrive", "Arriver", "🏫", "routine", 2465),
            _asset("routine_coat", "Manteau", "🧥", "routine", 2581),
            _asset("routine_hello", "Dire bonjour", "👋", "routine", 2748),
            _asset("routine_sit", "S’asseoir", "🪑", "routine", 2436),
            _asset("routine_work", "Travailler", "📘", "routine", 2577),
        ],
    },
    {
        "theme": "Le soir",
        "steps": [
            _asset("routine_tidy", "Ranger", "🧸", "routine", 2780),
            _asset("routine_bath", "Bain", "🛁", "routine", 2395),
            _asset("routine_pajamas", "Pyjama", "🌙", "routine", 2640),
            _asset("routine_story", "Histoire", "📖", "routine", 2577),
            _asset("routine_sleep", "Dormir", "🛏️", "routine", 2392),
        ],
    },
]

PROGRESSIVE_ROUTINES = [
    {
        "theme": "Le matin",
        "steps": [
            _asset("routine_wake", "Se réveiller", "⏰", "routine", 8989),
            _asset("routine_wash", "Se laver", "🚿", "routine", 34826),
            _asset("routine_dress", "S'habiller", "👕", "routine", 6627),
            _asset("routine_breakfast", "Petit déjeuner", "🥣", "routine", 4626),
            _asset("routine_brush_teeth", "Se brosser les dents", "🪥", "routine", 2326),
            _asset("routine_bag", "Prendre le sac", "🎒", "routine", 2475),
            _asset("routine_arrive", "Arriver à l'école", "🏫", "routine", 16807),
        ],
    },
    {
        "theme": "À l'école",
        "steps": [
            _asset("routine_arrive", "Arriver", "🏫", "routine", 16807),
            _asset("routine_coat", "Enlever le manteau", "🧥", "routine", 2242),
            _asset("routine_hello", "Dire bonjour", "👋", "routine", 6944),
            _asset("routine_sit", "S'asseoir", "🪑", "routine", 6611),
            _asset("routine_work", "Travailler", "📘", "routine", 6624),
            _asset("routine_recess", "Aller en récréation", "🛝", "routine", 6204),
            _asset("routine_tidy", "Ranger", "🧸", "routine", 2872),
        ],
    },
    {
        "theme": "Le soir",
        "steps": [
            _asset("routine_tidy", "Ranger", "🧸", "routine", 2872),
            _asset("routine_bath", "Prendre un bain", "🛁", "routine", 6058),
            _asset("routine_pajamas", "Mettre le pyjama", "🌙", "routine", 2522),
            _asset("routine_brush_teeth", "Se brosser les dents", "🪥", "routine", 2326),
            _asset("routine_story", "Lire une histoire", "📖", "routine", 25191),
            _asset("routine_listen", "Écouter calmement", "👂", "routine", 6572),
            _asset("routine_sleep", "Dormir", "🛏️", "routine", 6479),
        ],
    },
]


MEMORY_THEMES = [
    ("Animaux", ANIMALS),
    ("Nourriture", FOOD),
    ("École", SCHOOL),
    ("Maison", HOME),
    ("Émotions", EMOTIONS),
    ("Actions", ACTIONS),
]

SEARCH_THEMES = [
    ("Objets de la maison", HOME + ACTIONS),
    ("École", SCHOOL),
    ("Nourriture", FOOD),
    ("Animaux", ANIMALS),
]

RECOGNITION_THEMES = [
    ("Animaux", ANIMALS),
    ("Objets", HOME + SCHOOL + FOOD),
    ("Actions", ACTIONS),
    ("Émotions", EMOTIONS),
]


def build_game_content(
    game: Game,
    level: int,
    challenge_rank: int | None = None,
) -> dict[str, Any]:
    rng = random.Random()
    normalized_title = _normalize(game.title)
    normalized_category = _normalize(game.category.name if game.category else "")
    safe_level = max(game.min_level, min(level, game.max_level))
    safe_challenge_rank = _safe_challenge_rank(safe_level, challenge_rank)

    if "sequence routine" in normalized_title:
        content = _routine_sequence_content(rng, safe_challenge_rank)
    elif "memoire" in normalized_category:
        content = _memory_content(
            rng,
            safe_challenge_rank,
            ("Émotions", EMOTIONS) if "emotion" in normalized_title
            else ("Animaux", ANIMALS) if "anima" in normalized_title
            else None,
        )
    elif "concentration" in normalized_category:
        content = _search_content(rng, safe_challenge_rank)
    elif "logique" in normalized_category and "classe" in normalized_title:
        content = _odd_one_content(rng, safe_challenge_rank)
    elif "logique" in normalized_category:
        content = _logic_sequence_content(rng, safe_challenge_rank)
    elif "reconnaissance" in normalized_category:
        content = _recognition_content(
            rng,
            safe_challenge_rank,
            ("Couleurs", COLORS) if "couleur" in normalized_title
            else ("Animaux", ANIMALS) if "anima" in normalized_title
            else None,
        )
    elif "association" in normalized_category:
        content = _association_content(
            rng,
            safe_challenge_rank,
            EMOTION_NEEDS if "emotion" in normalized_title else OBJECT_USES,
        )
    else:
        content = _memory_content(rng, safe_challenge_rank)

    return {
        "game_id": game.id,
        "game_title": game.title,
        "content_version": CONTENT_VERSION,
        "session_id": _session_id(game.id),
        "level": safe_level,
        "challenge_rank": safe_challenge_rank,
        "max_challenge_rank": MAX_CHALLENGE_RANK,
        **content,
    }


def _memory_content(
    rng: random.Random,
    challenge_rank: int,
    forced_theme: tuple[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    count = _count_by_rank(
        challenge_rank,
        [3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10],
    )
    if forced_theme is not None and len(forced_theme[1]) >= count:
        theme, pool = forced_theme
    else:
        eligible_themes = [entry for entry in MEMORY_THEMES if len(entry[1]) >= count]
        if eligible_themes:
            theme, pool = rng.choice(eligible_themes)
        else:
            theme, pool = "Défi mixte", _unique_assets(
                ANIMALS + FOOD + SCHOOL + HOME + EMOTIONS + ACTIONS
            )
    selected = _sample(rng, pool, count)
    return {
        "mode": "memory_pairs",
        "theme": theme,
        "instructions": "Retrouve les paires identiques",
        "rounds": [
            {
                "id": "memory-session",
                "type": "memory_pairs",
                "instruction": "Retrouve les paires identiques",
                "items": selected,
                "metadata": {"pair_count": count},
            }
        ],
    }


def _search_content(rng: random.Random, challenge_rank: int) -> dict[str, Any]:
    grid_size = _count_by_rank(
        challenge_rank,
        [4, 5, 6, 7, 8, 9, 10, 11, 12, 12, 12, 12, 12, 12, 12],
    )
    rounds_count = _count_by_rank(
        challenge_rank,
        [3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 7, 8, 9, 10, 11],
    )
    eligible_themes = [entry for entry in SEARCH_THEMES if len(entry[1]) >= grid_size]
    theme, pool = rng.choice(eligible_themes or SEARCH_THEMES)
    rounds = []
    used_targets: set[str] = set()

    for index in range(rounds_count):
        items = _sample(rng, pool, grid_size)
        available_targets = [item for item in items if item["id"] not in used_targets]
        target = rng.choice(available_targets or items)
        used_targets.add(target["id"])
        rounds.append(
            {
                "id": f"search-{index + 1}",
                "type": "search_target",
                "instruction": f"Trouve {target['label'].lower()}",
                "prompt": target,
                "answer": target,
                "items": _shuffle(rng, items),
            }
        )

    return {
        "mode": "search_target",
        "theme": theme,
        "instructions": "Trouve l’image demandée",
        "rounds": rounds,
    }


def _recognition_content(
    rng: random.Random,
    challenge_rank: int,
    forced_theme: tuple[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if forced_theme is not None:
        theme, pool = forced_theme
    else:
        theme, pool = rng.choice(RECOGNITION_THEMES)

    rounds_count = _count_by_rank(
        challenge_rank,
        [4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 10],
    )
    choice_count = _count_by_rank(
        challenge_rank,
        [2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 6],
    )
    rounds = []

    for index, answer in enumerate(_sample(rng, pool, rounds_count)):
        distractors = [item for item in pool if item["id"] != answer["id"]]
        choices = _shuffle(rng, [answer, *_sample(rng, distractors, choice_count - 1)])
        rounds.append(
            {
                "id": f"recognition-{index + 1}",
                "type": "recognition_choice",
                "instruction": "Choisis la bonne réponse",
                "prompt": answer,
                "answer": answer,
                "choices": choices,
            }
        )

    return {
        "mode": "recognition_choice",
        "theme": theme,
        "instructions": "Choisis la bonne réponse",
        "rounds": rounds,
    }


def _logic_sequence_content(rng: random.Random, challenge_rank: int) -> dict[str, Any]:
    themes = [
        ("Couleurs", COLORS[:6]),
        ("Animaux", ANIMALS[:6]),
        ("Nourriture", FOOD[:6]),
        ("École", SCHOOL[:6]),
    ]
    theme, pool = rng.choice(themes)
    rounds_count = _count_by_rank(
        challenge_rank,
        [3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10],
    )
    pattern_size = _count_by_rank(
        challenge_rank,
        [2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4],
    )
    sequence_length = _count_by_rank(
        challenge_rank,
        [4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 10],
    )
    choice_count = _count_by_rank(
        challenge_rank,
        [3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6],
    )
    rounds = []

    for index in range(rounds_count):
        pattern = _sample(rng, pool, pattern_size)
        sequence = (pattern * 5)[:sequence_length]
        answer = pattern[len(sequence) % len(pattern)]
        distractors = [item for item in pool if item["id"] != answer["id"]]
        choices = _shuffle(
            rng,
            [answer, *_sample(rng, distractors, choice_count - 1)],
        )
        rounds.append(
            {
                "id": f"logic-sequence-{index + 1}",
                "type": "sequence_next",
                "instruction": "Qu’est-ce qui vient ensuite ?",
                "sequence": sequence,
                "answer": answer,
                "choices": choices,
            }
        )

    return {
        "mode": "sequence_next",
        "theme": theme,
        "instructions": "Complète la suite",
        "rounds": rounds,
    }


def _odd_one_content(rng: random.Random, challenge_rank: int) -> dict[str, Any]:
    groups = [
        ("Animaux", ANIMALS, FOOD),
        ("Nourriture", FOOD, SCHOOL),
        ("École", SCHOOL, ANIMALS),
        ("Maison", HOME, COLORS),
        ("Actions", ACTIONS, FOOD),
    ]
    rounds_count = _count_by_rank(
        challenge_rank,
        [3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10],
    )
    item_count = _count_by_rank(
        challenge_rank,
        [4, 4, 4, 5, 5, 5, 6, 6, 6, 7, 7, 7, 8, 8, 8],
    )
    rounds = []

    for index in range(rounds_count):
        theme, main_pool, odd_pool = rng.choice(groups)
        odd = rng.choice(odd_pool)
        items = _shuffle(rng, [*_sample(rng, main_pool, item_count - 1), odd])
        rounds.append(
            {
                "id": f"odd-one-{index + 1}",
                "type": "odd_one_out",
                "instruction": "Trouve l’intrus",
                "answer": odd,
                "items": items,
                "metadata": {"theme": theme},
            }
        )

    return {
        "mode": "odd_one_out",
        "theme": "Catégories",
        "instructions": "Trouve l’intrus",
        "rounds": rounds,
    }


def _association_content(
    rng: random.Random,
    challenge_rank: int,
    pool: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    count = _count_by_rank(
        challenge_rank,
        [3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 8, 8, 8],
    )
    selected = _sample(rng, pool, count)
    pairs = [{"left": left, "right": right} for left, right in selected]
    return {
        "mode": "association_pairs",
        "theme": "Associations",
        "instructions": "Associe les cartes qui vont ensemble",
        "rounds": [
            {
                "id": "association-session",
                "type": "association_pairs",
                "instruction": "Associe les cartes qui vont ensemble",
                "pairs": pairs,
            }
        ],
    }


def _routine_sequence_content(
    rng: random.Random,
    challenge_rank: int,
) -> dict[str, Any]:
    scenario = rng.choice(PROGRESSIVE_ROUTINES)
    count = _count_by_rank(
        challenge_rank,
        [3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 7, 7, 7, 7, 7],
    )
    sequence = scenario["steps"][:count]
    return {
        "mode": "routine_sequence",
        "theme": scenario["theme"],
        "instructions": "Remets les étapes dans l’ordre",
        "rounds": [
            {
                "id": "routine-sequence-session",
                "type": "routine_sequence",
                "instruction": "Remets les étapes dans l’ordre",
                "sequence": sequence,
                "items": _shuffle(rng, sequence),
            }
        ],
    }


def _count_by_rank(challenge_rank: int, values: list[int]) -> int:
    index = max(0, min(challenge_rank - 1, len(values) - 1))
    return values[index]


def _safe_challenge_rank(level: int, challenge_rank: int | None) -> int:
    first_rank = min(((level - 1) * CHALLENGES_PER_LEVEL) + 1, MAX_CHALLENGE_RANK)
    last_rank = min(first_rank + CHALLENGES_PER_LEVEL - 1, MAX_CHALLENGE_RANK)
    return max(first_rank, min(challenge_rank or first_rank, last_rank))


def _unique_assets(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return list({item["id"]: item for item in values}.values())


def _sample(
    rng: random.Random,
    values: list[Any],
    count: int,
) -> list[Any]:
    if count >= len(values):
        return _shuffle(rng, values)
    return rng.sample(values, count)


def _shuffle(rng: random.Random, values: list[Any]) -> list[Any]:
    shuffled = list(values)
    rng.shuffle(shuffled)
    return shuffled


def _normalize(value: str) -> str:
    replacements = {
        "à": "a",
        "â": "a",
        "ä": "a",
        "ç": "c",
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "û": "u",
        "ü": "u",
    }
    normalized = value.lower()
    for src, target in replacements.items():
        normalized = normalized.replace(src, target)
    return normalized


def _session_id(game_id: int) -> str:
    now = datetime.now(timezone.utc)
    return f"game-{game_id}-{int(now.timestamp() * 1000)}"
