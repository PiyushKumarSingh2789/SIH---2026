"""
DUPLICATE_SIMILARITY detector. Weight: 10%.

Runs ONCE per risk run across the whole project corpus (not per-project),
per PRD Section 6 formula:
  Duplicate Similarity = 0.60*text + 0.25*geographic + 0.15*attribute

Text: TF-IDF cosine similarity over title + description + location.
Geographic: Haversine proximity -- full similarity within GEO_FULL_KM, zero
  beyond GEO_ZERO_KM. If either project in a pair has no coordinates, the
  geo term is dropped and text/attribute weights are rebalanced -- never
  fabricated (PRD VAL-008: "no valid coordinates -> geo analysis unavailable").
Attribute: mean of 4 binary checks -- work_type, agency, cost band, and
  sanction-date window (PRD: "cost band, and sanction-date window").

NEVER call a result "confirmed duplicate" anywhere -- always "candidate".
"""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

TEXT_WEIGHT, GEO_WEIGHT, ATTR_WEIGHT = 0.60, 0.25, 0.15
GEO_FULL_KM, GEO_ZERO_KM = 0.5, 5.0   # full similarity within 500m, zero beyond 5km
DATE_WINDOW_DAYS = 180
SHOW_THRESHOLD = 0.60
MAX_CANDIDATES_PER_PROJECT = 3
COST_BANDS = [1_000_000, 2_500_000, 5_000_000, 10_000_000, 25_000_000]


def _ui_label(score: float) -> str:
    if score >= 0.85:
        return "very_strong"
    if score >= 0.75:
        return "strong"
    return "possible"


def _cost_band(amount: float) -> int:
    for i, b in enumerate(COST_BANDS):
        if amount < b:
            return i
    return len(COST_BANDS)


def _haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def compute_duplicate_candidates(rows: list[dict]) -> dict[str, list[dict]]:
    n = len(rows)
    candidates: dict[str, list[dict]] = {r["project_id"]: [] for r in rows}
    if n < 2:
        return candidates

    corpus = [
        " ".join(filter(None, [r.get("title"), r.get("description"), r.get("state"), r.get("district")]))
        for r in rows
    ]
    tfidf = TfidfVectorizer(stop_words="english", max_features=5000).fit_transform(corpus)
    text_sim = cosine_similarity(tfidf)

    lat = np.array([r.get("latitude") if r.get("latitude") is not None else np.nan for r in rows])
    lon = np.array([r.get("longitude") if r.get("longitude") is not None else np.nan for r in rows])
    has_geo = ~np.isnan(lat) & ~np.isnan(lon)
    lat1, lat2 = np.meshgrid(lat, lat, indexing="ij")
    lon1, lon2 = np.meshgrid(lon, lon, indexing="ij")
    dist_km = _haversine_km(lat1, lon1, lat2, lon2)
    geo_sim = np.clip(1 - (dist_km - GEO_FULL_KM) / max(GEO_ZERO_KM - GEO_FULL_KM, 1e-6), 0, 1)
    geo_valid = np.outer(has_geo, has_geo)

    work_types = [r.get("work_type") for r in rows]
    agencies = [r.get("agency_name") for r in rows]
    cost_bands = [_cost_band(r.get("sanctioned_amount") or 0) for r in rows]
    sanction_dates = [r.get("sanction_date") for r in rows]
    codes = [r.get("project_code") for r in rows]
    ids = [r.get("project_id") for r in rows]

    for i in range(n):
        for j in range(i + 1, n):
            attr_hits = 0
            if work_types[i] and work_types[i] == work_types[j]:
                attr_hits += 1
            if agencies[i] and agencies[i] == agencies[j]:
                attr_hits += 1
            if cost_bands[i] == cost_bands[j]:
                attr_hits += 1
            if sanction_dates[i] and sanction_dates[j] and abs((sanction_dates[i] - sanction_dates[j]).days) <= DATE_WINDOW_DAYS:
                attr_hits += 1
            attr_score = attr_hits / 4

            t = float(text_sim[i, j])
            if geo_valid[i, j]:
                g = float(geo_sim[i, j])
                combined = TEXT_WEIGHT * t + GEO_WEIGHT * g + ATTR_WEIGHT * attr_score
                geo_available, geo_note = True, round(g, 3)
            else:
                w_text = TEXT_WEIGHT / (TEXT_WEIGHT + ATTR_WEIGHT)
                w_attr = ATTR_WEIGHT / (TEXT_WEIGHT + ATTR_WEIGHT)
                combined = w_text * t + w_attr * attr_score
                geo_available, geo_note = False, None

            if combined < SHOW_THRESHOLD:
                continue

            ui_label = _ui_label(combined)
            geo_phrase = f"geo {round(geo_note * 100)}%" if geo_available else "no coordinates on one or both projects"
            base_expl = (
                f"{combined * 100:.0f}% combined similarity to {{other_code}} "
                f"(text {t * 100:.0f}%, {geo_phrase}, attributes {attr_score * 100:.0f}%) -- "
                f"review as a possible duplicate, not a confirmed one."
            )

            entry_i = {
                "candidate_project_id": ids[j], "candidate_project_code": codes[j],
                "text_similarity": round(t, 3), "geographic_similarity": geo_note,
                "attribute_similarity": round(attr_score, 3), "combined_score": round(combined, 3),
                "ui_label": ui_label, "geo_data_available": geo_available,
                "explanation": base_expl.format(other_code=codes[j]),
            }
            entry_j = {**entry_i, "candidate_project_id": ids[i], "candidate_project_code": codes[i],
                       "explanation": base_expl.format(other_code=codes[i])}

            candidates[ids[i]].append(entry_i)
            candidates[ids[j]].append(entry_j)

    for pid in candidates:
        candidates[pid] = sorted(candidates[pid], key=lambda c: c["combined_score"], reverse=True)[:MAX_CANDIDATES_PER_PROJECT]

    return candidates


def duplicate_factor_result(project_candidates: list[dict]) -> dict:
    """Converts a project's candidate list into a RiskFactorResult-shaped dict.
    Always computed -- even an empty result -- since the corpus-wide comparison always runs
    for every project, unlike the data-dependent detectors that get skipped."""
    if not project_candidates:
        return {
            "raw_value": 0.0, "normalized_score": 0.0,
            "evidence": {"candidates_found": 0},
            "explanation": "No other project in the current dataset scored above the 60% similarity threshold.",
        }
    top = project_candidates[0]
    normalized = round(top["combined_score"] * 100, 2)
    return {
        "raw_value": normalized, "normalized_score": normalized,
        "evidence": {"candidates_found": len(project_candidates), "top_candidates": project_candidates},
        "explanation": top["explanation"],
    }
