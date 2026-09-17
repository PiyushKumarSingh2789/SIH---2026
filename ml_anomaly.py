"""
ML_ANOMALY detector. Weight: 10% (capped -- statistical unusualness only,
never framed as a verdict, per PRD Section 5: "statistical unusualness only
and limited to 10% score weight").

Runs ONCE per risk run over the whole project feature matrix, per PRD
Section 6 configuration:
  n_estimators=200, contamination=0.08, random_state=42
Pipeline: median-impute -> winsorize (1st/99th pct clip) -> RobustScaler -> IsolationForest.

Features (PRD: "cost, sanction, utilization, utilization ratio, progress,
gap, deviation, lag, payment count/amount/interval, peer deviation"):
  sanctioned_amount, elapsed_days, utilized_amount, utilization_ratio,
  physical_progress_percent, progress_expenditure_gap, cost_deviation_percent,
  progress_lag, payment_count, payment_amount_total, payment_interval_avg_days,
  peer_deviation_score

Skipped entirely if the dataset is too small to fit a meaningful model.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import RobustScaler

N_ESTIMATORS = 200
CONTAMINATION = 0.08
RANDOM_STATE = 42
MIN_PROJECTS = 30

FEATURE_COLUMNS = [
    "sanctioned_amount", "elapsed_days", "utilized_amount", "utilization_ratio",
    "physical_progress_percent", "progress_expenditure_gap", "cost_deviation_percent",
    "progress_lag", "payment_count", "payment_amount_total", "payment_interval_avg_days",
    "peer_deviation_score",
]


def compute_ml_anomaly_scores(df: pd.DataFrame) -> dict[str, dict]:
    if len(df) < MIN_PROJECTS:
        return {}

    available_cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    X_raw = df[available_cols].apply(pd.to_numeric, errors="coerce")
    imputed_mask = X_raw.isna()

    X_imputed = SimpleImputer(strategy="median").fit_transform(X_raw)

    # Winsorize at 1st/99th percentile so a single extreme value doesn't dominate scaling.
    lower = np.percentile(X_imputed, 1, axis=0)
    upper = np.percentile(X_imputed, 99, axis=0)
    X_winsorized = np.clip(X_imputed, lower, upper)

    X_scaled = RobustScaler().fit_transform(X_winsorized)

    model = IsolationForest(n_estimators=N_ESTIMATORS, contamination=CONTAMINATION, random_state=RANDOM_STATE)
    model.fit(X_scaled)
    decision_scores = model.decision_function(X_scaled)  # lower = more anomalous

    ranks = pd.Series(decision_scores).rank(pct=True)  # 1.0 = most normal, ~0 = most anomalous
    normalized_scores = (1 - ranks) * 100

    results: dict[str, dict] = {}
    project_ids = df["project_id"].tolist()
    for idx, pid in enumerate(project_ids):
        imputed_features = [c for c, was_imputed in zip(available_cols, imputed_mask.iloc[idx]) if was_imputed]
        pct_rank = round(float(1 - ranks.iloc[idx]) * 100, 1)
        results[pid] = {
            "raw_value": round(float(decision_scores[idx]), 4),
            "normalized_score": round(float(normalized_scores.iloc[idx]), 2),
            "evidence": {
                "features_used": available_cols,
                "features_imputed": imputed_features,
                "anomaly_percentile_rank": pct_rank,
                "n_estimators": N_ESTIMATORS, "contamination": CONTAMINATION,
                "random_state": RANDOM_STATE, "dataset_size": len(df),
            },
            "explanation": (
                f"Statistical pattern across {len(available_cols)} financial/execution/payment "
                f"features ranks in the top {pct_rank:.0f}% most unusual out of {len(df)} projects "
                f"scored in this run (Isolation Forest -- a statistical signal only, not evidence "
                f"of wrongdoing)."
            ),
        }
    return results
