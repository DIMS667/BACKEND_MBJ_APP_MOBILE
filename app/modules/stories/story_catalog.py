from typing import Any


def _picto(pictogram_id: int) -> str:
    return (
        f"https://static.arasaac.org/pictograms/"
        f"{pictogram_id}/{pictogram_id}_300.png"
    )


def _choice(
    label: str,
    pictogram_id: int,
    next_page: int,
    order: int,
) -> dict[str, Any]:
    return {
        "label": label,
        "pictogram_url": _picto(pictogram_id),
        "next_page_number": next_page,
        "sort_order": order,
    }


def _page(
    number: int,
    text: str,
    pictogram_id: int,
    *,
    next_page: int | None = None,
    choices: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "page_number": number,
        "text": text,
        "image_url": None,
        "pictogram_url": _picto(pictogram_id),
        "animation_type": "fade",
        "next_page_number": next_page,
        "choices": choices or [],
    }


STORIES_SPRINT_1_DATA = [
    {
        "title": "Je me prépare pour l'école",
        "description": "Les étapes simples avant de partir à l'école.",
        "category": "school",
        "cover_url": _picto(16807),
        "pages": [
            _page(1, "Je me réveille.", 8989),
            _page(
                2,
                "J'ai du mal à me motiver pour me lever.",
                30391,
                choices=[
                    _choice("Compter doucement puis me lever", 2486, 3, 0),
                    _choice("Demander de l'aide pour démarrer", 32648, 4, 1),
                ],
            ),
            _page(3, "Je compte doucement puis je me lève.", 2486, next_page=5),
            _page(4, "Un adulte m'aide à démarrer la journée.", 32648, next_page=5),
            _page(5, "Je m'habille.", 6627),
            _page(6, "Je prends mon petit déjeuner.", 4626),
            _page(7, "Je prends mon sac.", 2475),
            _page(8, "J'arrive à l'école.", 16807),
        ],
    },
    {
        "title": "Je demande de l'aide en classe",
        "description": "Que faire lorsqu'un exercice est difficile.",
        "category": "school",
        "cover_url": _picto(32648),
        "pages": [
            _page(1, "Je commence mon travail en classe.", 6624),
            _page(
                2,
                "Je ne comprends pas une consigne.",
                30391,
                choices=[
                    _choice("Demander de l'aide", 32648, 3, 0),
                    _choice("Respirer puis demander", 2486, 4, 1),
                ],
            ),
            _page(3, "Je dis : J'ai besoin d'aide.", 32648, next_page=5),
            _page(4, "Je respire, puis je lève la main.", 2486, next_page=5),
            _page(5, "L'enseignant vient m'expliquer.", 6556),
            _page(6, "Je reprends mon travail calmement.", 6624),
            _page(7, "Je suis fier d'avoir demandé.", 31408),
        ],
    },
    {
        "title": "Je vais chez le médecin",
        "description": "Découvrir une visite médicale étape par étape.",
        "category": "doctor",
        "cover_url": _picto(6561),
        "pages": [
            _page(1, "Je vais chez le médecin.", 6561),
            _page(2, "J'attends dans la salle d'attente.", 37336),
            _page(
                3,
                "L'attente peut sembler longue.",
                30391,
                choices=[
                    _choice("Regarder un livre en attendant", 25191, 4, 0),
                    _choice("Respirer calmement", 2486, 5, 1),
                ],
            ),
            _page(4, "Je regarde un livre pendant que j'attends.", 25191, next_page=6),
            _page(5, "Je respire calmement en attendant.", 2486, next_page=6),
            _page(6, "Le médecin m'appelle.", 6561),
            _page(7, "Il m'examine doucement.", 6561),
            _page(8, "La visite est terminée.", 35547),
        ],
    },
    {
        "title": "Je vais chez le dentiste",
        "description": "Comprendre les étapes d'un examen des dents.",
        "category": "doctor",
        "cover_url": _picto(2733),
        "pages": [
            _page(1, "J'arrive chez le dentiste avec un adulte.", 2733),
            _page(2, "Je m'assois sur le fauteuil.", 6611),
            _page(
                3,
                "Je peux avoir un peu peur.",
                10261,
                choices=[
                    _choice("Dire que j'ai peur", 10261, 4, 0),
                    _choice("Respirer calmement", 2486, 5, 1),
                ],
            ),
            _page(4, "Je dis au dentiste ce que je ressens.", 10261, next_page=6),
            _page(5, "Je respire lentement avant l'examen.", 2486, next_page=6),
            _page(6, "Le dentiste regarde mes dents doucement.", 2733),
            _page(7, "Je repars avec des dents bien soignées.", 2326),
        ],
    },
    {
        "title": "Je reconnais mes émotions",
        "description": "Mettre un mot simple sur ce que je ressens.",
        "category": "emotions",
        "cover_url": _picto(35547),
        "pages": [
            _page(1, "Parfois, je suis content.", 35547),
            _page(2, "Parfois, je suis triste.", 35545),
            _page(3, "Parfois, je suis fâché.", 35539),
            _page(4, "Parfois, j'ai peur.", 10261),
            _page(
                5,
                "Je peux choisir comment le dire.",
                30391,
                choices=[
                    _choice("Le dire avec des mots", 32648, 6, 0),
                    _choice("Respirer avant de le dire", 2486, 7, 1),
                ],
            ),
            _page(6, "Je dis mon émotion avec des mots simples.", 32648, next_page=8),
            _page(7, "Je respire, puis je trouve les mots.", 2486, next_page=8),
            _page(8, "Je peux dire ce que je ressens.", 31408),
        ],
    },
    {
        "title": "Je demande une pause",
        "description": "Identifier la surcharge et choisir une action calme.",
        "category": "emotions",
        "cover_url": _picto(31310),
        "pages": [
            _page(1, "Il y a beaucoup d'informations autour de moi.", 30391),
            _page(2, "Mon corps devient tendu et je me sens inquiet.", 30391),
            _page(
                3,
                "Je choisis une action qui peut m'aider.",
                32648,
                choices=[
                    _choice("Dire ce que je ressens", 35539, 4, 0),
                    _choice("Respirer calmement", 2486, 5, 1),
                    _choice("Demander une pause", 32648, 6, 2),
                ],
            ),
            _page(4, "Je nomme mon émotion à un adulte.", 35539, next_page=7),
            _page(5, "Je ralentis ma respiration quelques instants.", 2486, next_page=7),
            _page(6, "Je demande une pause dans un endroit calme.", 32648, next_page=7),
            _page(7, "Mon corps retrouve peu à peu son calme.", 31310),
            _page(8, "Je reprends quand je me sens prêt.", 31408),
        ],
    },
    {
        "title": "Mon emploi du temps change",
        "description": "Comprendre qu'un programme peut être modifié.",
        "category": "change",
        "cover_url": _picto(31955),
        "pages": [
            _page(1, "Aujourd'hui, le programme change.", 31955),
            _page(2, "Je peux être inquiet.", 30391),
            _page(
                3,
                "Je choisis comment réagir.",
                31955,
                choices=[
                    _choice("Poser une question à l'adulte", 32648, 4, 0),
                    _choice("Respirer avant d'écouter", 2486, 5, 1),
                ],
            ),
            _page(4, "Je demande ce qui va changer.", 32648, next_page=6),
            _page(5, "Je respire avant d'écouter les explications.", 2486, next_page=6),
            _page(6, "Un adulte m'explique le nouveau programme.", 32648),
            _page(7, "Je regarde ce qui va se passer.", 31955),
            _page(8, "Je peux essayer ce nouveau programme.", 31408),
        ],
    },
    {
        "title": "Une nouvelle personne arrive",
        "description": "Se préparer à rencontrer une personne inconnue.",
        "category": "change",
        "cover_url": _picto(6944),
        "pages": [
            _page(1, "Une nouvelle personne vient à la maison.", 6964),
            _page(2, "Je ne la connais pas encore.", 30391),
            _page(
                3,
                "Je choisis comment prendre mon temps.",
                36914,
                choices=[
                    _choice("Poser une question", 32648, 4, 0),
                    _choice("Observer un moment", 36914, 5, 1),
                ],
            ),
            _page(4, "Je demande à l'adulte qui est cette personne.", 32648, next_page=6),
            _page(5, "Je reste près d'un adulte et j'observe.", 36914, next_page=6),
            _page(6, "Je peux dire bonjour quand je suis prêt.", 6944),
            _page(7, "Je connais maintenant un peu mieux cette personne.", 35547),
        ],
    },
    {
        "title": "J'attends mon tour",
        "description": "Apprendre à patienter pendant une activité.",
        "category": "frustration",
        "cover_url": _picto(36914),
        "pages": [
            _page(1, "Je veux jouer maintenant.", 23392),
            _page(2, "Une autre personne joue avant moi.", 23392),
            _page(
                3,
                "Attendre peut être difficile.",
                30391,
                choices=[
                    _choice("Respirer pendant que j'attends", 2486, 4, 0),
                    _choice("Regarder le jeu en attendant", 23392, 5, 1),
                ],
            ),
            _page(4, "Je respire doucement pendant que j'attends.", 2486, next_page=6),
            _page(5, "Je regarde le jeu pendant que j'attends.", 23392, next_page=6),
            _page(6, "Maintenant, c'est mon tour.", 35547),
        ],
    },
    {
        "title": "Je perds à un jeu",
        "description": "Traverser la déception sans rester bloqué.",
        "category": "frustration",
        "cover_url": _picto(35539),
        "pages": [
            _page(1, "Je joue avec une autre personne.", 23392),
            _page(2, "Cette fois, je ne gagne pas la partie.", 35545),
            _page(
                3,
                "Je ressens une forte frustration. Que faire ?",
                35539,
                choices=[
                    _choice("Respirer lentement", 2486, 4, 0),
                    _choice("Dire que je suis déçu", 35545, 5, 1),
                    _choice("Demander une pause", 32648, 6, 2),
                ],
            ),
            _page(4, "Je prends plusieurs respirations lentes.", 2486, next_page=7),
            _page(5, "Je dis calmement que je suis déçu.", 35545, next_page=7),
            _page(6, "Je fais une courte pause pour me calmer.", 31310, next_page=7),
            _page(7, "Perdre une partie ne change pas qui je suis.", 31408),
            _page(8, "Je pourrai jouer une autre fois.", 23392),
        ],
    },
    {
        "title": "Je prépare mon coucher",
        "description": "Une routine calme avant de dormir.",
        "category": "sleep",
        "cover_url": _picto(6479),
        "pages": [
            _page(1, "Je range mes affaires.", 2872),
            _page(2, "J'éteins les écrans.", 25498),
            _page(3, "Je mets mon pyjama.", 2522),
            _page(4, "Je me brosse les dents.", 2326),
            _page(
                5,
                "Je choisis comment me calmer avant de dormir.",
                31310,
                choices=[
                    _choice("Écouter une histoire calme", 25191, 6, 0),
                    _choice("Respirer lentement dans mon lit", 2486, 7, 1),
                ],
            ),
            _page(6, "J'écoute une histoire calme.", 25191, next_page=8),
            _page(7, "Je respire lentement, allongé dans mon lit.", 2486, next_page=8),
            _page(8, "Je me couche pour dormir.", 6479),
        ],
    },
    {
        "title": "Je me réveille pendant la nuit",
        "description": "Retrouver le calme après un réveil nocturne.",
        "category": "sleep",
        "cover_url": _picto(8989),
        "pages": [
            _page(1, "Je dors dans mon lit.", 6479),
            _page(2, "Je me réveille pendant la nuit.", 8989),
            _page(
                3,
                "Je peux choisir une action rassurante.",
                10261,
                choices=[
                    _choice("Respirer dans mon lit", 2486, 4, 0),
                    _choice("Appeler doucement un adulte", 32648, 5, 1),
                ],
            ),
            _page(4, "Je respire lentement sous ma couverture.", 2486, next_page=6),
            _page(5, "Un adulte vient me rassurer calmement.", 32648, next_page=6),
            _page(6, "Je retrouve une position confortable.", 25900),
            _page(7, "Je peux me rendormir tranquillement.", 6479),
        ],
    },
    {
        "title": "Je me lave les mains",
        "description": "Les étapes pour avoir les mains propres.",
        "category": "hygiene",
        "cover_url": _picto(34826),
        "pages": [
            _page(1, "Mes mains ont besoin d'être lavées.", 34826),
            _page(2, "Je mouille mes mains avec de l'eau.", 32464),
            _page(
                3,
                "Le savon peut piquer un peu ou beaucoup mousser.",
                34826,
                choices=[
                    _choice("Frotter doucement", 34826, 4, 0),
                    _choice("Demander de l'aide pour le savon", 32648, 5, 1),
                ],
            ),
            _page(4, "Je frotte doucement mes mains avec du savon.", 34826, next_page=6),
            _page(5, "Un adulte m'aide à mettre le savon.", 32648, next_page=6),
            _page(6, "Je rince puis je sèche mes mains.", 32464),
            _page(7, "Mes mains sont propres.", 35547),
        ],
    },
    {
        "title": "Je me brosse les dents",
        "description": "Prendre soin de ses dents avec ou sans aide.",
        "category": "hygiene",
        "cover_url": _picto(2326),
        "pages": [
            _page(1, "Je vais dans la salle de bain.", 6058),
            _page(2, "Je prends ma brosse à dents.", 2694),
            _page(
                3,
                "Si c'est difficile, je choisis une solution.",
                30391,
                choices=[
                    _choice("Demander de l'aide", 32648, 4, 0),
                    _choice("Commencer doucement", 2326, 5, 1),
                ],
            ),
            _page(4, "Un adulte m'aide à commencer.", 32648, next_page=6),
            _page(5, "Je commence lentement, une zone après l'autre.", 2326, next_page=6),
            _page(6, "Je brosse toutes mes dents puis je rince.", 2326),
            _page(7, "J'ai pris soin de mes dents.", 31408),
        ],
    },
]
