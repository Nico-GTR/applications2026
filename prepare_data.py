# -*- coding: utf-8 -*-
"""
Préparation des données de candidatures d'alternance.

Lit le CSV brut, nettoie / normalise (regroupement des noms d'entreprises,
parsing des dates, reconstruction du funnel depuis l'historique), calcule
toutes les agrégations nécessaires au dashboard et écrit `dashboard_data.js`.

Usage :  python prepare_data.py
"""

import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime

# Console Windows : forcer l'UTF-8 pour les caractères accentués / flèches.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

CSV_PATH = "maestro_candidatures_alternance_2026_enrichi.csv"
OUT_JS = "dashboard_data.js"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )

def nkey(s: str) -> str:
    """Clé normalisée : minuscule, sans accent, espaces compactés."""
    return re.sub(r"\s+", " ", strip_accents(s or "").lower()).strip()

def parse_date(s: str):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%y %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None

# ---------------------------------------------------------------------------
# Normalisation des noms d'entreprises
# ---------------------------------------------------------------------------
# Règles par sous-chaîne (ordre important : les plus spécifiques d'abord).
COMPANY_RULES = [
    ("credit agricole", "Crédit Agricole"),
    ("cartier", "Richemont"),
    ("richemont", "Richemont"),
    ("thales", "Thales"),
    ("safran", "Safran"),
    ("airbus", "Airbus"),
    ("dassault", "Dassault Systèmes"),
    ("arianegroup", "ArianeGroup"),
    ("ariane group", "ArianeGroup"),
    ("canal", "Canal+"),
    ("valeo", "Valeo"),
    ("renault", "Renault"),
    ("alpine", "Alpine"),
    ("bnp paribas", "BNP Paribas"),
    ("amundi", "Amundi"),
    ("mbda", "MBDA"),
    ("framatome", "Framatome"),
    ("ge healthcare", "GE HealthCare"),
    ("biomerieux", "bioMérieux"),
    ("schneider", "Schneider Electric"),
    ("moet hennessy", "Moët Hennessy"),
    ("natixis", "Natixis"),
    ("groupe bpce", "Groupe BPCE"),
    ("amiad", "AMIAD"),
    ("nokia", "Nokia"),
    ("orange", "Orange"),
    ("harmattan", "Harmattan AI"),
    ("societe generale", "Société Générale Assurances"),
    ("credit mutuel", "Crédit Mutuel"),
    ("publicis", "Publicis Media"),
    ("axa", "AXA"),
    ("st gobain", "Saint-Gobain"),
    ("saint gobain", "Saint-Gobain"),
]

# Entreprise dont l'offre a finalement été acceptée (issue du pipeline).
# Renseigné à la main : le statut "Je suis pris" seul ne suffit pas à distinguer
# une offre acceptée d'une offre obtenue puis déclinée (plusieurs entreprises
# peuvent porter ce statut dans l'historique).
FINAL_OUTCOME_COMPANY = "Nokia"

# Noms canoniques propres pour les entreprises rencontrées une seule fois
# (corrige juste la casse / les fautes éventuelles).
CANON_SINGLE = {
    "horizon trading solution": "Horizon Trading Solutions",
    "afterdata": "Afterdata",
    "alten group": "ALTEN",
    "groupe sii": "Groupe SII",
    "ag2r la mondiale": "AG2R La Mondiale",
    "ansm": "ANSM",
}

def canonical_company(raw: str) -> str:
    k = nkey(raw)
    for sub, canon in COMPANY_RULES:
        if sub in k:
            return canon
    if k in CANON_SINGLE:
        return CANON_SINGLE[k]
    return re.sub(r"\s+", " ", (raw or "").strip())

# ---------------------------------------------------------------------------
# Funnel / étapes
# ---------------------------------------------------------------------------
STAGE_RANK = {
    "j'ai postule": 1,
    "j'ai un 1er entretien": 2,
    "j'ai un 2eme entretien": 3,
    "je suis pris": 4,
}
STAGE_LABELS = {
    1: "Candidature envoyée",
    2: "1er entretien",
    3: "2ème entretien",
    4: "Offre reçue",
}

def action_rank(action: str) -> int:
    return STAGE_RANK.get(nkey(action), 0)

# Thèmes de postes (un poste peut compter dans plusieurs thèmes)
ROLE_THEMES = [
    ("Data Scientist", ["data scientist", "data science"]),
    ("Data Engineer", ["data engineer", "data ingenieur", "data engineering", "ingenieur data", "data/ia", "data & ia", "data et ia"]),
    ("Data Analyst", ["data analyst", "analyste de donnees", "business analyst", "data analyste"]),
    ("Machine Learning", ["machine learning", "ml ops", "mlops", "ml engineer", " ml ", "apprentissage", "deep learning", "sciml"]),
    ("IA générative / LLM", ["generative", "generatif", "llm", "genai", "ia gen", "agents", "world model", "foundation", "fondation"]),
    ("Computer Vision", ["vision", "image", "traitement d'image", "imagerie"]),
    ("IA (général)", ["intelligence artificielle", " ia ", "ia ", " ia", "ai ", " ai", "ia/", "/ia"]),
    ("Robotique", ["robot", "robotique"]),
    ("Dév. logiciel", ["developpeur", "logiciel", "software", "developpement", "developer", "informatique"]),
    ("DevOps / Cloud", ["devops", "cloud", "aws"]),
]

def role_themes(poste: str):
    k = " " + nkey(poste) + " "
    found = []
    for label, keys in ROLE_THEMES:
        if any(key in k for key in keys):
            found.append(label)
    return found

FR_WEEKDAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
FR_MONTHS = ["", "janv.", "févr.", "mars", "avr.", "mai", "juin",
             "juil.", "août", "sept.", "oct.", "nov.", "déc."]

# ---------------------------------------------------------------------------
# Lecture + nettoyage
# ---------------------------------------------------------------------------

def main():
    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    records = []
    raw_to_canon = defaultdict(set)
    dup_keys = Counter()

    for r in rows:
        raw_company = (r.get("entreprise") or "").strip()
        company = canonical_company(raw_company)
        raw_to_canon[company].add(raw_company)

        poste = (r.get("poste") or "").strip()
        statut = (r.get("statut") or "").strip()
        applied = parse_date(r.get("date_candidature"))
        current = parse_date(r.get("date_dans_colonne_actuelle"))

        # Historique -> liste d'événements (date, action)
        history = []
        try:
            hj = json.loads(r.get("historique_json") or "[]")
            for ev in hj:
                d = parse_date(ev.get("date"))
                history.append({"date": d, "action": ev.get("action", "")})
        except (json.JSONDecodeError, TypeError):
            pass

        # Étape maximale atteinte (en ignorant "Refusé")
        max_stage = 1
        for ev in history:
            max_stage = max(max_stage, action_rank(ev["action"]))
        if not history:
            max_stage = 1

        rejected = nkey(statut) == "refuse"
        got_job = nkey(statut) == "je suis pris" or (r.get("jai_le_job", "").strip().lower() == "true")

        # Délai de première réponse : du "postulé" à la 1re action suivante
        first_response_days = None
        post_date = None
        for ev in history:
            if action_rank(ev["action"]) == 1 and ev["date"]:
                post_date = ev["date"]
                break
        if post_date is None:
            post_date = applied
        if post_date:
            next_dates = [ev["date"] for ev in history
                          if ev["date"] and ev["date"] > post_date]
            if next_dates:
                first_response_days = (min(next_dates) - post_date).days

        records.append({
            "company": company,
            "rawCompany": raw_company,
            "role": poste,
            "status": statut,
            "applied": applied,
            "current": current,
            "maxStage": max_stage,
            "rejected": rejected,
            "gotJob": got_job,
            "firstResponseDays": first_response_days,
            "themes": role_themes(poste),
        })

        if applied:
            dup_keys[(company, poste, applied.isoformat())] += 1

    # -------------------------------------------------------------------
    # Agrégations
    # -------------------------------------------------------------------
    total = len(records)
    companies = Counter(r["company"] for r in records)
    unique_companies = len(companies)

    # Funnel
    funnel = []
    for stage in (1, 2, 3, 4):
        cnt = sum(1 for r in records if r["maxStage"] >= stage)
        funnel.append({"stage": STAGE_LABELS[stage], "count": cnt})

    interviews = sum(1 for r in records if r["maxStage"] >= 2)
    second_int = sum(1 for r in records if r["maxStage"] >= 3)
    offers = sum(1 for r in records if r["maxStage"] >= 4)
    rejected_n = sum(1 for r in records if r["rejected"])
    pending = sum(1 for r in records if not r["rejected"] and not r["gotJob"])

    # Statut actuel (regroupé)
    status_dist = Counter(r["status"] for r in records)

    # Top entreprises (avec entretiens décrochés)
    comp_interviews = Counter()
    for r in records:
        if r["maxStage"] >= 2:
            comp_interviews[r["company"]] += 1
    top_companies = [
        {"company": c, "count": n, "interviews": comp_interviews.get(c, 0)}
        for c, n in companies.most_common(15)
    ]

    # Timeline quotidienne (pour heatmap) + hebdo (pour aire)
    daily = Counter()
    weekly = Counter()
    weekday = Counter()
    hour = Counter()
    for r in records:
        d = r["applied"]
        if not d:
            continue
        daily[d.strftime("%Y-%m-%d")] += 1
        iso = d.isocalendar()
        weekly[(iso[0], iso[1])] += 1
        weekday[d.weekday()] += 1
        hour[d.hour] += 1

    timeline_daily = [{"date": k, "count": v} for k, v in sorted(daily.items())]

    # Série hebdo continue (label = lundi de la semaine)
    weekly_sorted = sorted(weekly.items())
    weekly_series = []
    cumulative = 0
    for (yr, wk), v in weekly_sorted:
        monday = datetime.fromisocalendar(yr, wk, 1)
        cumulative += v
        weekly_series.append({
            "label": f"{monday.day} {FR_MONTHS[monday.month]}",
            "count": v,
            "cumulative": cumulative,
        })

    by_weekday = [{"day": FR_WEEKDAYS[i], "count": weekday.get(i, 0)} for i in range(7)]
    by_hour = [{"hour": h, "count": hour.get(h, 0)} for h in range(24)]

    # Délais de réponse
    resp = [r["firstResponseDays"] for r in records
            if r["firstResponseDays"] is not None and r["firstResponseDays"] >= 0]
    resp_sorted = sorted(resp)
    avg_resp = round(sum(resp) / len(resp), 1) if resp else 0
    median_resp = resp_sorted[len(resp_sorted) // 2] if resp_sorted else 0
    buckets = Counter()
    bucket_order = ["≤ 3 j", "4–7 j", "8–14 j", "15–30 j", "> 30 j"]
    for d in resp:
        if d <= 3:
            buckets["≤ 3 j"] += 1
        elif d <= 7:
            buckets["4–7 j"] += 1
        elif d <= 14:
            buckets["8–14 j"] += 1
        elif d <= 30:
            buckets["15–30 j"] += 1
        else:
            buckets["> 30 j"] += 1
    response_buckets = [{"bucket": b, "count": buckets.get(b, 0)} for b in bucket_order]

    # Thèmes de postes
    theme_counter = Counter()
    for r in records:
        for t in r["themes"]:
            theme_counter[t] += 1
    role_themes_out = [{"theme": t, "count": n} for t, n in theme_counter.most_common()]

    # Taux de conversion par entreprise (top par candidatures, min 3 candidatures)
    conv = []
    for c, n in companies.most_common():
        if n >= 3:
            iv = comp_interviews.get(c, 0)
            conv.append({
                "company": c, "applied": n, "interviews": iv,
                "rate": round(100 * iv / n, 0),
            })
    conv = sorted(conv, key=lambda x: (-x["rate"], -x["applied"]))[:12]

    # Issue finale : l'offre effectivement acceptée
    outcome_candidates = [
        r for r in records
        if r["company"] == FINAL_OUTCOME_COMPANY and r["maxStage"] >= 4
    ]
    outcome = None
    if outcome_candidates:
        r = sorted(outcome_candidates, key=lambda x: x["applied"] or datetime.min)[0]
        outcome = {
            "company": r["company"],
            "role": r["role"],
            "applied": r["applied"].strftime("%d/%m/%Y") if r["applied"] else "",
            "responseDays": r["firstResponseDays"],
        }

    # Doublons exacts
    duplicates = sum(v - 1 for v in dup_keys.values() if v > 1)

    dates_all = [r["applied"] for r in records if r["applied"]]
    date_min = min(dates_all)
    date_max = max(dates_all)

    # Records détaillés (pour la table interactive)
    apps_out = []
    for r in sorted(records, key=lambda x: (x["applied"] or datetime.min), reverse=True):
        apps_out.append({
            "company": r["company"],
            "role": r["role"],
            "status": r["status"],
            "applied": r["applied"].strftime("%d/%m/%Y") if r["applied"] else "",
            "appliedISO": r["applied"].strftime("%Y-%m-%d") if r["applied"] else "",
            "maxStage": r["maxStage"],
            "responseDays": r["firstResponseDays"],
        })

    data = {
        "meta": {
            "total": total,
            "uniqueCompanies": unique_companies,
            "duplicates": duplicates,
            "dateMin": date_min.strftime("%d/%m/%Y"),
            "dateMax": date_max.strftime("%d/%m/%Y"),
            "generatedAt": datetime.now().strftime("%d/%m/%Y %H:%M"),
        },
        "kpis": {
            "total": total,
            "uniqueCompanies": unique_companies,
            "interviews": interviews,
            "interviewRate": round(100 * interviews / total, 1) if total else 0,
            "secondInterviews": second_int,
            "offers": offers,
            "rejected": rejected_n,
            "rejectRate": round(100 * rejected_n / total, 1) if total else 0,
            "pending": pending,
            "avgResponse": avg_resp,
            "medianResponse": median_resp,
        },
        "funnel": funnel,
        "statusDistribution": [{"status": s, "count": n}
                               for s, n in status_dist.most_common()],
        "topCompanies": top_companies,
        "timelineDaily": timeline_daily,
        "weeklySeries": weekly_series,
        "byWeekday": by_weekday,
        "byHour": by_hour,
        "responseBuckets": response_buckets,
        "roleThemes": role_themes_out,
        "companyConversion": conv,
        "applications": apps_out,
        "outcome": outcome,
    }

    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write("// Généré automatiquement par prepare_data.py — ne pas éditer à la main.\n")
        f.write("const DASHBOARD_DATA = ")
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    # -------------------------------------------------------------------
    # Rapport de préparation (console)
    # -------------------------------------------------------------------
    print("=" * 64)
    print("  PRÉPARATION DES DONNÉES — rapport")
    print("=" * 64)
    print(f"  Candidatures lues ............ {total}")
    print(f"  Entreprises (après regroupt.). {unique_companies}")
    print(f"  Doublons exacts détectés ..... {duplicates}")
    print(f"  Période ...................... {data['meta']['dateMin']} → {data['meta']['dateMax']}")
    print(f"  Entretiens décrochés ......... {interviews}  ({data['kpis']['interviewRate']} %)")
    print(f"  2èmes entretiens ............. {second_int}")
    print(f"  Offres reçues ................ {offers}")
    print(f"  Refus ........................ {rejected_n}  ({data['kpis']['rejectRate']} %)")
    print(f"  En cours ..................... {pending}")
    print(f"  Délai moyen de réponse ....... {avg_resp} j (médiane {median_resp} j)")
    if outcome:
        print(f"  Issue finale .................. {outcome['company']} — {outcome['role']}")
    print("-" * 64)
    print("  Regroupements d'entreprises (variantes -> canonique) :")
    merged = {c: v for c, v in raw_to_canon.items() if len(v) > 1}
    for canon, variants in sorted(merged.items(), key=lambda x: -len(x[1])):
        print(f"   • {canon:<22} <- {', '.join(sorted(variants))}")
    print("-" * 64)
    print(f"  Fichier généré : {OUT_JS}")
    print("=" * 64)


if __name__ == "__main__":
    sys.exit(main())
