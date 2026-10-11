# Lot 6B-A3.2 — routage d'intentions local

`ToolRouter.route()` construit un `ToolRouteResult` local et déterministe. Il n'exécute pas d'outil. Les priorités sont : météo avec localisation, écritures Calendar, lectures Calendar, écritures Tasks, lecture Tasks, puis aucun match.

Les écritures incomplètes restent des intentions avec `needs_clarification=True` et une raison explicite. Aucun titre, date, heure ou cible n'est inventé. Les références `demain` et jours français sont résolues à partir de la date locale courante ; les créations avec une date et une heure explicites reçoivent des valeurs ISO locales et un créneau d'une heure lorsqu'aucune fin n'est fournie. Les opérations update/delete conservent une cible textuelle à résoudre lors du lot d'orchestration suivant.

Compatibilité : `execute_for` reste le point de compatibilité de l'AgentService pré-A3.3 pour la météo déjà existante. Le nouveau chemin `route` testé par ce lot n'appelle jamais le registry ni un handler.

Validation : A1/A2/A3.1/A3.2 et streaming 18/18 ; suite native 119/119 ; strict lot 1 37/37 ; zéro `.pyc` sous `src` et `tests`. Aucun accès réseau, OAuth ou SDK Google n'est introduit. Prochaine étape autorisable : A3.3, orchestration AgentService explicite.