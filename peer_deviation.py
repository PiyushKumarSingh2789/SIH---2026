"""
PEER_DEVIATION detector. Weight: 10%.

Distinct from COST_DEVIATION (cost only): this factor looks at EXECUTION PACE
(progress lag against the PRD's expected-progress formula) and PAYMENT CADENCE
(payment count) relative to the same work_type/district/state/national peer
hierarchy used for cost -- so a project can look normal on cost alone but be a
clear outlier in how it is actually being executed and paid for.

Uses a robust (median/IQR) deviation, not a raw average, per PRD Section 6.
Skipped entirely for a project if no peer group at any level reaches the
minimum sample size for either metric.
"""
import pandas as pd

MIN_SAMPLE_SIZE = 10
METRICS = ["progress_lag", "payment_count"]
LEVELS = [
    ("district", ["work_type", "state", "district", "sanction_year"]),
    ("state_year", ["work_type", "state", "sanction_year"]),
    ("state", ["work_type", "state"]),
    ("national", ["work_type"]),
]

_METRIC_LABELS = {
    "progress_lag": "execution pace (progress lag)",
    "payment_count": "payment cadence (payment count)",
}


def _group_stats(df: pd.DataFrame, group_cols: list[str], value_col: str) -> dict:
    valid = df.dropna(subset=[value_col] + group_cols)
    if valid.empty:
        return {}
    out = {}
    for key, series in valid.groupby(group_cols)[value_col]:
        if len(series) < MIN_SAMPLE_SIZE:
            continue
        key_tuple = key if isinstance(key, tuple) else (key,)
        median = float(series.median())
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        # Floor the IQR relative to the median (not a bare epsilon) -- a peer group where
        # everyone has the same integer payment_count has a "true" IQR of 0, but treating
        # that as near-infinite precision produces absurd robust-z multipliers. Flooring
        # at 10% of the median (min 1.0) keeps deviations meaningful without exploding.
        iqr = max(float(q3 - q1), abs(median) * 0.1, 1.0)
        out[key_tuple] = {"median": median, "iqr": iqr, "count": int(len(series))}
    return out


def build_peer_deviation_lookup(df: pd.DataFrame) -> dict:
    """Precomputes group stats for every metric at every hierarchy level, once per run."""
    return {metric: {level: _group_stats(df, cols, metric) for level, cols in LEVELS} for metric in METRICS}


def _find_group(row: pd.Series, lookup_for_metric: dict):
    for level, cols in LEVELS:
        key = tuple(row.get(c) for c in cols)
        if any(v is None or (isinstance(v, float) and pd.isna(v)) for v in key):
            continue
        stats = lookup_for_metric[level].get(key)
        if stats:
            return {**stats, "level": level}
    return None


def compute_peer_deviation(row: pd.Series, lookup: dict) -> dict | None:
    sub_results = []
    for metric in METRICS:
        value = row.get(metric)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            continue
        group = _find_group(row, lookup[metric])
        if not group:
            continue
        z = (value - group["median"]) / group["iqr"]
        normalized = min(100.0, max(0.0, abs(z) * 40))
        sub_results.append({
            "metric": metric, "value": round(float(value), 2), "peer_median": round(group["median"], 2),
            "peer_sample_count": group["count"], "peer_group_level": group["level"],
            "robust_z": round(float(z), 2), "normalized": normalized,
        })

    if not sub_results:
        return None

    normalized_score = sum(r["normalized"] for r in sub_results) / len(sub_results)
    parts = [
        f"{_METRIC_LABELS.get(r['metric'], r['metric'])} deviates {abs(r['robust_z']):.1f}x the typical "
        f"peer spread (value {r['value']:.1f} vs peer median {r['peer_median']:.1f}, "
        f"{r['peer_sample_count']} {r['peer_group_level']}-level peers)"
        for r in sub_results
    ]
    explanation = "; ".join(parts) + "."
    explanation = explanation[0].upper() + explanation[1:]

    return {
        "raw_value": round(normalized_score, 2),
        "normalized_score": round(normalized_score, 2),
        "evidence": {"metrics": sub_results},
        "explanation": explanation,
    }
