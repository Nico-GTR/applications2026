# Candidatures Alternance 2026 — Dashboard

Tableau de bord de suivi de ma recherche d'alternance 2026 (Data / IA) : **270 candidatures** envoyées à **78 entreprises**, du premier envoi jusqu'à l'entretien décroché — et l'alternance finalement retenue, chez **Nokia**.

Pas de framework, pas de build : une page HTML/CSS/JS statique, alimentée par des données pré-calculées à partir d'un export CSV personnel.

![thème clair / sombre](https://img.shields.io/badge/theme-light%20%2F%20dark-7c8cff)
![no build step](https://img.shields.io/badge/build-none-34d399)

## Aperçu

- **Pipeline de conversion** — funnel candidature → 1er entretien → 2ème entretien → offre
- **Résultat final** — où tout ça a mené
- **Activité dans le temps** — série hebdomadaire + cumul, calendrier façon heatmap GitHub
- **Délais de réponse** — distribution en buckets, moyenne/médiane
- **Top entreprises** & **taux de conversion en entretien** par entreprise
- **Les 10 plus grosses entreprises visées** — classement par effectif mondial réel (donnée externe, curée à la main), pas par volume de candidatures
- **Thèmes de postes** visés (Data Scientist, ML, IA générative, etc.), extraits par mots-clés
- **Table interactive** — recherche et filtres par statut
- Thème clair / sombre, entièrement responsive

## Stack technique

- **Frontend** — HTML/CSS/JS vanilla + [Chart.js](https://www.chartjs.org/) (via CDN), aucune dépendance à installer
- **Préparation des données** — Python 3 (bibliothèque standard uniquement)

## Structure du projet

```
dashboard.html        interface du dashboard (structure, style, logique d'affichage)
dashboard_data.js      données agrégées, générées par prepare_data.py (inclus, prêt à l'emploi)
prepare_data.py         lit le CSV brut, nettoie/normalise, calcule les agrégats et écrit dashboard_data.js
```

## Lancer en local

Aucun serveur requis : ouvrez simplement `dashboard.html` dans un navigateur. `dashboard_data.js` déjà généré est inclus dans le dépôt.

## Régénérer les données

Le CSV brut n'est **pas** versionné (il contient des données personnelles). Pour régénérer `dashboard_data.js` à partir de votre propre export :

1. Placez un export CSV nommé `maestro_candidatures_alternance_2026_enrichi.csv` à la racine, avec au minimum les colonnes `entreprise`, `poste`, `statut`, `date_candidature`, `date_dans_colonne_actuelle`, `historique_json`, `jai_le_job`.
2. Lancez :
   ```
   python prepare_data.py
   ```
3. Rechargez `dashboard.html`.

Le script regroupe automatiquement les variantes de noms d'entreprises (ex. filiales, fautes de frappe), reconstruit le funnel depuis l'historique d'actions, et calcule les KPIs, délais de réponse, thèmes de postes, etc.

Deux informations ne viennent pas du CSV et sont renseignées à la main dans `prepare_data.py` : l'entreprise dont l'offre a été acceptée (`FINAL_OUTCOME_COMPANY`), et les effectifs mondiaux approximatifs des plus grandes entreprises visées (`COMPANY_HEADCOUNT`, sources publiques 2025).

## Confidentialité

Le CSV source (`*.csv`) est exclu du dépôt via `.gitignore` : il peut contenir des colonnes ou notes plus détaillées que ce qui est réellement affiché. Seules les données déjà agrégées dans `dashboard_data.js` sont publiées — les noms d'entreprises y sont volontairement conservés tels quels.

## Licence

[MIT](LICENSE)
