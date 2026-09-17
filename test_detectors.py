"""
Unit tests for the four detectors added to bring the risk engine from 3/7 to 7/7
factors: PAYMENT_ANOMALY, PEER_DEVIATION, DUPLICATE_SIMILARITY, ML_ANOMALY.

These are pure-function tests against synthetic data -- no database or FastAPI
app required -- so they run fast and don't need MySQL to validate detector logic.
Run with: pytest app/tests/test_detectors.py -v
"""
from datetime import date

import pandas as pd

from app.services.detectors.payment_anomaly import compute_payment_anomaly
from app.services.detectors.peer_deviation import build_peer_deviation_lookup, compute_peer_deviation
from app.services.detectors.duplicate_similarity import compute_duplicate_candidates, duplicate_factor_result
from app.services.detectors.ml_anomaly import compute_ml_anomaly_scores


class _FakePayment:
    def __init__(self, payment_date, payment_amount):
        self.payment_date = payment_date
        self.payment_amount = payment_amount


# ---------------------------------------------------------------- payment_anomaly

def test_payment_anomaly_skipped_when_no_payments():
    assert compute_payment_anomaly([], date(2023, 1, 1), None, False, 1_000_000, 0) is None


def test_payment_anomaly_clean_history_scores_low():
    payments = [_FakePayment(date(2023, 2, 1), 100_000), _FakePayment(date(2023, 5, 1), 150_000)]
    result = compute_payment_anomaly(payments, date(2023, 1, 1), None, False, 1_000_000, 250_000)
    assert result["normalized_score"] < 20


def test_payment_anomaly_flags_pre_sanction_payment():
    payments = [_FakePayment(date(2022, 12, 1), 500_000), _FakePayment(date(2023, 5, 1), 150_000)]
    result = compute_payment_anomaly(payments, date(2023, 1, 1), None, False, 1_000_000, 650_000)
    assert result["normalized_score"] >= 50
    assert result["evidence"]["pre_sanction_payment_count"] == 1


# ---------------------------------------------------------------- peer_deviation

def _peer_group_df(outlier_lag=80.0, outlier_payment_count=1):
    rows = [
        {"project_id": f"p{i}", "work_type": "Road", "state": "UP", "district": "Lucknow",
         "sanction_year": 2023, "progress_lag": 5.0 + i * 0.1, "payment_count": 3}
        for i in range(15)
    ]
    rows.append({"project_id": "outlier", "work_type": "Road", "state": "UP", "district": "Lucknow",
                 "sanction_year": 2023, "progress_lag": outlier_lag, "payment_count": outlier_payment_count})
    return pd.DataFrame(rows)


def test_peer_deviation_flags_execution_outlier():
    df = _peer_group_df()
    lookup = build_peer_deviation_lookup(df)
    outlier_row = df[df.project_id == "outlier"].iloc[0]
    result = compute_peer_deviation(outlier_row, lookup)
    assert result is not None
    assert result["normalized_score"] > 50


def test_peer_deviation_normal_project_scores_low():
    df = _peer_group_df()
    lookup = build_peer_deviation_lookup(df)
    normal_row = df[df.project_id == "p0"].iloc[0]
    result = compute_peer_deviation(normal_row, lookup)
    assert result is not None
    assert result["normalized_score"] < 50


def test_peer_deviation_skipped_below_min_sample_size():
    # Only 3 peers -- below MIN_SAMPLE_SIZE=10 at every hierarchy level.
    df = pd.DataFrame([
        {"project_id": f"q{i}", "work_type": "Bridge", "state": "Bihar", "district": "Patna",
         "sanction_year": 2023, "progress_lag": 5.0, "payment_count": 3}
        for i in range(3)
    ])
    lookup = build_peer_deviation_lookup(df)
    row = df.iloc[0]
    assert compute_peer_deviation(row, lookup) is None


# ---------------------------------------------------------------- duplicate_similarity

def _duplicate_rows():
    return [
        {"project_id": "a", "project_code": "PC-A", "title": "Construction of community hall in Ward 5",
         "description": "Building a new community hall for public use", "work_type": "Building",
         "agency_name": "PWD", "state": "UP", "district": "Lucknow", "latitude": 26.85, "longitude": 80.95,
         "sanctioned_amount": 2_000_000, "sanction_date": date(2023, 1, 1)},
        {"project_id": "b", "project_code": "PC-B", "title": "Construction of community hall Ward 5 area",
         "description": "Building a community hall for public utility", "work_type": "Building",
         "agency_name": "PWD", "state": "UP", "district": "Lucknow", "latitude": 26.851, "longitude": 80.951,
         "sanctioned_amount": 2_050_000, "sanction_date": date(2023, 1, 15)},
        {"project_id": "c", "project_code": "PC-C", "title": "Road repair near market",
         "description": "Repairing damaged road surface", "work_type": "Road",
         "agency_name": "Municipal Corp", "state": "UP", "district": "Kanpur", "latitude": 26.45, "longitude": 80.33,
         "sanctioned_amount": 900_000, "sanction_date": date(2023, 3, 1)},
    ]


def test_duplicate_similarity_finds_near_identical_pair():
    candidates = compute_duplicate_candidates(_duplicate_rows())
    assert len(candidates["a"]) >= 1
    top = candidates["a"][0]
    assert top["candidate_project_id"] == "b"
    assert top["combined_score"] >= 0.60
    assert top["ui_label"] in {"strong", "very_strong"}


def test_duplicate_similarity_never_labels_confirmed():
    # The explanation text is allowed to say "not a confirmed one" (that's the point --
    # it explicitly disclaims certainty) but must never assert "confirmed duplicate".
    candidates = compute_duplicate_candidates(_duplicate_rows())
    for cand_list in candidates.values():
        for c in cand_list:
            assert "confirmed" not in c["ui_label"]
            assert "confirmed duplicate" not in c["explanation"].lower()


def test_duplicate_factor_result_empty_when_no_candidates():
    result = duplicate_factor_result([])
    assert result["normalized_score"] == 0.0


def test_duplicate_similarity_dissimilar_project_has_no_candidates():
    candidates = compute_duplicate_candidates(_duplicate_rows())
    assert candidates["c"] == []


# ---------------------------------------------------------------- ml_anomaly

def _ml_rows(n_normal=40):
    rows = [
        {"project_id": f"m{i}", "sanctioned_amount": 1_000_000 + i * 1000, "elapsed_days": 200,
         "utilized_amount": 500_000, "utilization_ratio": 0.5, "physical_progress_percent": 50.0,
         "progress_expenditure_gap": 5.0, "cost_deviation_percent": 2.0, "progress_lag": 5.0,
         "payment_count": 3, "payment_amount_total": 500_000, "payment_interval_avg_days": 60.0,
         "peer_deviation_score": 10.0}
        for i in range(n_normal)
    ]
    rows.append({
        "project_id": "outlier_ml", "sanctioned_amount": 50_000_000, "elapsed_days": 1000,
        "utilized_amount": 49_000_000, "utilization_ratio": 0.98, "physical_progress_percent": 5.0,
        "progress_expenditure_gap": 93.0, "cost_deviation_percent": 400.0, "progress_lag": 90.0,
        "payment_count": 40, "payment_amount_total": 49_000_000, "payment_interval_avg_days": 2.0,
        "peer_deviation_score": 95.0,
    })
    return pd.DataFrame(rows)


def test_ml_anomaly_ranks_outlier_above_normal():
    df = _ml_rows()
    results = compute_ml_anomaly_scores(df)
    assert results["outlier_ml"]["normalized_score"] > results["m0"]["normalized_score"]


def test_ml_anomaly_skipped_below_min_projects():
    df = _ml_rows(n_normal=5)  # 6 total, below MIN_PROJECTS=30
    assert compute_ml_anomaly_scores(df) == {}


def test_ml_anomaly_scores_bounded_0_to_100():
    df = _ml_rows()
    results = compute_ml_anomaly_scores(df)
    for r in results.values():
        assert 0.0 <= r["normalized_score"] <= 100.0
