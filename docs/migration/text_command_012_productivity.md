# Lot 012 — Mail, Calendar et Contacts

Le routeur Native reconnaît désormais les commandes de lecture prouvées :

- Mail : liste, recherche et lecture par identifiant ;
- Calendar : agenda/upcoming, jour courant ou lendemain, recherche ;
- Contacts : liste, recherche et lecture par identifiant.

Le bridge appelle les services existants et publie un résultat structuré sans
PreparedAction. Les fournisseurs indisponibles produisent un état local
explicite ; aucune réponse Gmail/Calendar n’est inventée par le LLM.

Les écritures Gmail et Calendar restent désactivées et classées
`DEFERRED_GOVERNED_GOOGLE_WRITE_CAPABILITIES`. Les mutations Contacts ne sont
pas ajoutées dans ce lot faute de preuve Native complète de la chaîne UI et
de validation live test-owned.

Validation : `test_text_command_012_productivity.py` 6/6, régressions Text
Command 006/010/011 et PC Read vertes, QML Native 5/5, Lot 1 53/53. Computer
Use était indisponible (`apps=[]`), donc les statuts live restent bloqués
par la surface externe.
