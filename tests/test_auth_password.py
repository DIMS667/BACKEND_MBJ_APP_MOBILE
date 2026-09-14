"""Règle de mot de passe — AUTH-01.

Le serveur n'imposait **rien** : `password: str`, sans contrainte. Le
formulaire d'inscription annonçait pourtant « 8 caractères minimum, dont
1 chiffre » tout en n'en refusant que moins de 6, et l'écran de
réinitialisation promettait « au moins 6 caractères ». Trois règles
différentes pour une seule exigence, dont la plus visible était fausse.
"""

import inspect

import pytest
from fastapi import HTTPException

from app.modules.auth.service import (
    PASSWORD_MIN_LENGTH,
    PASSWORD_RULE_MESSAGE,
    ensure_password_is_strong_enough,
    register_user,
    reset_password,
)


@pytest.mark.parametrize(
    "mot_de_passe",
    [
        "",
        "abc",
        "abcdef",      # acceptable pour l'ancienne validation locale (< 6)
        "abcdefg",     # sept caractères : un de moins que la consigne
        "abcdefgh",    # huit caractères mais aucun chiffre
        "12345",       # des chiffres, mais trop court
    ],
)
def test_refuse_ce_que_la_consigne_dit_de_refuser(mot_de_passe):
    with pytest.raises(HTTPException) as refus:
        ensure_password_is_strong_enough(mot_de_passe)
    assert refus.value.status_code == 400
    assert refus.value.detail == PASSWORD_RULE_MESSAGE


@pytest.mark.parametrize(
    "mot_de_passe",
    ["abcdefg1", "12345678", "Maison2026!", "  espace1  "],
)
def test_accepte_ce_que_la_consigne_dit_d_accepter(mot_de_passe):
    ensure_password_is_strong_enough(mot_de_passe)


def test_le_message_dit_la_regle_entiere():
    assert str(PASSWORD_MIN_LENGTH) in PASSWORD_RULE_MESSAGE
    assert "chiffre" in PASSWORD_RULE_MESSAGE
    # Le frontend affiche mot pour mot la même exigence
    # (`lib/features/auth/domain/password_rule.dart`).
    assert PASSWORD_MIN_LENGTH == 8


def test_la_regle_est_appliquee_a_la_creation_et_a_la_reinitialisation():
    """Les deux chemins qui **créent** un mot de passe la traversent.

    Vérifié sur la source plutôt qu'en montant une base : ce qui importe
    ici est qu'aucun des deux ne puisse enregistrer un mot de passe sans
    être passé par la règle.
    """
    for fonction in (register_user, reset_password):
        source = inspect.getsource(fonction)
        assert "ensure_password_is_strong_enough" in source, fonction.__name__


def test_la_reinitialisation_verifie_avant_de_consommer_le_code():
    """Un mot de passe refusé ne doit pas brûler le code reçu par email.

    Sinon le parent devrait en redemander un pour une simple faute de
    saisie.
    """
    source = inspect.getsource(reset_password)
    position_regle = source.index("ensure_password_is_strong_enough")
    position_usage = source.index("reset_code.used = True")
    assert position_regle < position_usage


def test_la_connexion_ne_revalide_pas_le_mot_de_passe():
    """Un compte créé avant cette règle doit rester accessible.

    La règle ne s'applique qu'à la création : l'imposer à la connexion
    enfermerait dehors le propriétaire d'un mot de passe plus ancien.
    """
    from app.modules.auth.service import login_user

    assert "ensure_password_is_strong_enough" not in inspect.getsource(login_user)
