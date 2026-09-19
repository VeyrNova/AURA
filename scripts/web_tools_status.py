"""Read-only AURA Web Tools status. Makes no network request."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from security.permissions import Permission
from security.policy_engine import SecurityPolicyEngine
from tools.web_search import ddgs_available, ddgs_version


def yn(value: bool) -> str:
    return "Oui" if value else "Non"


def main() -> int:
    policy = SecurityPolicyEngine(db=None)
    free_ready = bool(
        settings.INTERNET_TOOLS_ENABLED
        and settings.WEB_SEARCH_ENABLED
        and settings.FREE_WEB_SEARCH_ENABLED
        and ddgs_available()
    )
    print("=== AURA v0.7.2.1 — WEB TOOLS STATUS ===")
    print("Lecture seule : aucune requête Internet n'est effectuée.\n")
    print(f"Outils Internet          : {yn(settings.INTERNET_TOOLS_ENABLED)}")
    print(f"Météo Open-Meteo         : {yn(settings.WEATHER_TOOL_ENABLED)}")
    print(f"Lecture URL explicite    : {yn(settings.WEB_FETCH_ENABLED)}")
    print(f"Recherche Web            : {yn(settings.WEB_SEARCH_ENABLED)}")
    print(f"Recherche zéro coût      : {yn(settings.FREE_WEB_SEARCH_ENABLED)}")
    print(f"DDGS installé            : {yn(ddgs_available())} ({ddgs_version()})")
    print(f"Backends autorisés       : {settings.FREE_WEB_SEARCH_BACKENDS}")
    print(f"Région                   : {settings.FREE_WEB_SEARCH_REGION}")
    print(f"Synthèse Groq optionnelle: {yn(settings.FREE_WEB_SEARCH_SYNTHESIS_ENABLED and settings.GROQ_ENABLED and bool(settings.GROQ_API_KEY))}")
    print(f"Fallback payant          : Non")
    print(f"Permission WEB_READ      : {yn(Permission.WEB_READ in policy.granted_permissions)}")
    print(f"EXTERNAL_NETWORK brut    : {yn(Permission.EXTERNAL_NETWORK in policy.granted_permissions)}")
    print("\nGarde-fous HTTP :")
    print(f"  timeout lecture URL    : {settings.WEB_HTTP_TIMEOUT:.1f}s")
    print(f"  timeout recherche      : {settings.FREE_WEB_SEARCH_TIMEOUT_SECONDS:.1f}s / backend")
    print(f"  taille réponse max     : {settings.WEB_MAX_RESPONSE_BYTES} octets")
    print(f"  redirections max       : {settings.WEB_MAX_REDIRECTS}")
    print(f"  texte page max         : {settings.WEB_FETCH_MAX_TEXT_CHARS} caractères")
    if settings.INTERNET_TOOLS_ENABLED and Permission.WEB_READ in policy.granted_permissions:
        print("\n[PASS] Couche Internet contrôlée prête.")
        if free_ready:
            print("[PASS] Recherche Web zéro coût prête via DDGS; aucun compte de recherche/API payante requis.")
        else:
            print("[INFO] Installe DDGS avec INSTALLER_RECHERCHE_WEB_GRATUITE.bat pour activer la recherche générale.")
        return 0
    print("\n[FAIL] Couche Internet désactivée ou permission WEB_READ absente.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
