"""
Risk engine orchestrator. Implements the pipeline from PRD Section 5:
raw data -> feature engineering -> peer groups -> detectors -> weighted score -> explanation.

All 7 defined factors are now implemented:
  COST_DEVIATION, PROGRESS_EXPENDITURE_MISMATCH, DELAY_STALL, PAYMENT_ANOMALY (per-project),
  PEER_DEVIATION, ML_ANOMALY, DUPLICATE_SIMILARITY (batch, run once across the whole corpus).
The formula still rebalances over whatever IS computed for a given project -- a project
missing payment history, for example, still gets scored fairly over its other factors.

CRITICAL: every recompute creates a NEW RiskRun + new RiskScore/RiskFactorResult rows.
Never update existing risk_scores rows -- see PRD storage requirement on immutability.
"""
from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Project, RiskRun, RiskScore, RiskFactorResult, PeerBenchmark, DuplicateCandidate,
    FactorCode, FACTOR_WEIGHTS, RiskLevel, ProjectStatus,
)
from app.services.peer_stats import compute_peer_stats
from app.services.feature_engineering import build_feature_row
from app.services.detectors.cost_deviation import compute_cost_deviation
from app.services.detectors.mismatch import compute_mismatch
from app.services.detectors.stall import compute_stall
from app.services.detectors.payment_anomaly import compute_payment_anomaly
from app.services.detectors.peer_deviation import build_peer_deviation_lookup, compute_peer_deviation
from app.services.detectors.duplicate_similarity import compute_duplicate_candidates, duplicate_factor_result
from app.services.detectors.ml_anomaly import compute_ml_anomaly_scores

RISK_ENGINE_VERSION = "v1.1.0"   # bumped: 7/7 factors now implemented (was v1.0.0 at 3/7)
DETECTOR_VERSION = "v1.1.0"
TOTAL_DEFINED_FACTORS = len(FACTOR_WEIGHTS)  # 7 -- evidence completeness is always measured against all 7


def _risk_level(score: float) -> RiskLevel:
    if score >= 80:
        return RiskLevel.CRITICAL
    if score >= 60:
        return RiskLevel.HIGH
    if score >= 30:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _load_projects(db: Session) -> list[Project]:
    """One bulk query with eager-loaded relationships, so the batch detectors don't
    trigger N+1 queries across 1,500+ projects."""
    return (
        db.query(Project)
        .options(
            selectinload(Project.location),
            selectinload(Project.agency),
            selectinload(Project.financials),
            selectinload(Project.progress_reports),
            selectinload(Project.payments),
        )
        .all()
    )


def run_risk_engine(db: Session, triggered_by_user_id: str | None = None,
                     as_of: date | None = None) -> RiskRun:
    """Scores every project in the DB and returns the completed RiskRun. This is what
    POST /risk/recompute calls. Always creates new rows -- never mutates prior runs."""
    as_of = as_of or date.today()

    risk_run = RiskRun(engine_version=RISK_ENGINE_VERSION, triggered_by_user_id=triggered_by_user_id)
    db.add(risk_run)
    db.flush()  # get risk_run.id without committing yet

    projects = _load_projects(db)

    # ---- Phase 1: per-project local detectors (COST_DEVIATION, MISMATCH, STALL, PAYMENT_ANOMALY)
    #      + build the shared feature row every batch detector below reads from. ----
    per_project_factors: dict[str, list[dict]] = {p.id: [] for p in projects}
    feature_rows: list[dict] = []
    peer_benchmarks_seen: dict[tuple, dict] = {}

    for project in projects:
        latest_financial = max(project.financials, key=lambda f: f.as_of_date, default=None)
        latest_progress = max(project.progress_reports, key=lambda pr: pr.report_date, default=None)
        payments = list(project.payments)

        feature_row = build_feature_row(
            project, project.location, project.agency, latest_financial, latest_progress, payments, as_of,
        )
        feature_rows.append(feature_row)
        factors = per_project_factors[project.id]

        # --- COST_DEVIATION ---
        peer = compute_peer_stats(
            db, work_type=project.work_type,
            state=project.location.state if project.location else None,
            district=project.location.district if project.location else None,
            sanction_year=project.sanction_date.year if project.sanction_date else None,
        )
        if peer:
            result = compute_cost_deviation(float(project.sanctioned_amount), peer)
            factors.append({"factor_code": FactorCode.COST_DEVIATION, **result})
            feature_row["cost_deviation_percent"] = result["raw_value"]
            bench_key = (peer.group_level, peer.group_value, project.work_type)
            peer_benchmarks_seen[bench_key] = {
                "work_type": project.work_type, "group_level": peer.group_level, "group_value": peer.group_value,
                "sample_count": peer.sample_count, "median_cost": peer.median_cost,
                "iqr_low": peer.iqr_low, "iqr_high": peer.iqr_high,
            }

        # --- PROGRESS_EXPENDITURE_MISMATCH ---
        if latest_financial and latest_progress:
            result = compute_mismatch(
                float(latest_financial.utilized_amount), float(project.sanctioned_amount),
                latest_progress.physical_progress_percent,
            )
            factors.append({"factor_code": FactorCode.PROGRESS_EXPENDITURE_MISMATCH, **result})

        # --- DELAY_STALL ---
        reports = [(pr.report_date, pr.physical_progress_percent) for pr in project.progress_reports]
        stall_result = compute_stall(reports, as_of=as_of, is_completed=(project.status == ProjectStatus.COMPLETED))
        if stall_result:
            factors.append({"factor_code": FactorCode.DELAY_STALL, **stall_result})

        # --- PAYMENT_ANOMALY ---
        payment_result = compute_payment_anomaly(
            payments, sanction_date=project.sanction_date, actual_completion_date=project.actual_completion_date,
            is_completed=(project.status == ProjectStatus.COMPLETED), sanctioned_amount=float(project.sanctioned_amount),
            utilized_amount=float(latest_financial.utilized_amount) if latest_financial else 0.0,
        )
        if payment_result:
            factors.append({"factor_code": FactorCode.PAYMENT_ANOMALY, **payment_result})

    # ---- Phase 2: batch-level detectors across the whole corpus ----
    features_df = pd.DataFrame(feature_rows)

    # PEER_DEVIATION first -- its output feeds ML_ANOMALY as a feature (PRD feature list
    # explicitly includes "peer deviation").
    peer_dev_lookup = build_peer_deviation_lookup(features_df)
    peer_dev_results: dict[str, dict | None] = {}
    for _, row in features_df.iterrows():
        peer_dev_results[row["project_id"]] = compute_peer_deviation(row, peer_dev_lookup)

    features_df["peer_deviation_score"] = features_df["project_id"].map(
        lambda pid: peer_dev_results[pid]["normalized_score"] if peer_dev_results.get(pid) else None
    )

    ml_results = compute_ml_anomaly_scores(features_df)
    duplicate_candidates_by_project = compute_duplicate_candidates(feature_rows)

    for pid, factors in per_project_factors.items():
        peer_dev_result = peer_dev_results.get(pid)
        if peer_dev_result:
            factors.append({"factor_code": FactorCode.PEER_DEVIATION, **peer_dev_result})

        ml_result = ml_results.get(pid)
        if ml_result:
            factors.append({"factor_code": FactorCode.ML_ANOMALY, **ml_result})

        dup_result = duplicate_factor_result(duplicate_candidates_by_project.get(pid, []))
        factors.append({"factor_code": FactorCode.DUPLICATE_SIMILARITY, **dup_result})

    # ---- Phase 3: weighted final score, rebalanced over whatever WAS computed, + persistence ----
    for project in projects:
        factor_results = per_project_factors[project.id]
        if factor_results:
            weighted_sum = sum(FACTOR_WEIGHTS[f["factor_code"]] * f["normalized_score"] for f in factor_results)
            weight_sum = sum(FACTOR_WEIGHTS[f["factor_code"]] for f in factor_results)
            final_score = weighted_sum / weight_sum
        else:
            final_score = 0.0  # no evidence at all -- profile-only, per PRD "0-29 Low: project profile only"

        risk_score = RiskScore(
            risk_run_id=risk_run.id,
            project_id=project.id,
            final_score=round(final_score, 2),
            risk_level=_risk_level(final_score),
            factors_computed_count=len(factor_results),
            evidence_completeness_percent=round(len(factor_results) / TOTAL_DEFINED_FACTORS * 100, 1),
        )
        db.add(risk_score)
        db.flush()

        for f in factor_results:
            db.add(RiskFactorResult(
                risk_score_id=risk_score.id,
                factor_code=f["factor_code"],
                raw_value=f["raw_value"],
                normalized_score=f["normalized_score"],
                weight=FACTOR_WEIGHTS[f["factor_code"]],
                contribution=round(FACTOR_WEIGHTS[f["factor_code"]] * f["normalized_score"], 2),
                evidence=f["evidence"],
                explanation=f["explanation"],
                detector_version=DETECTOR_VERSION,
            ))

    # Snapshot peer benchmarks used in this run, for durable audit evidence (PRD: "store
    # actual peer group and sample count as evidence").
    for bench in peer_benchmarks_seen.values():
        db.add(PeerBenchmark(risk_run_id=risk_run.id, **bench))

    # Persist duplicate candidates found in this run. Never "confirmed duplicate" -- always a candidate.
    for pid, dup_candidates in duplicate_candidates_by_project.items():
        for c in dup_candidates:
            db.add(DuplicateCandidate(
                project_id=pid,
                candidate_project_id=c["candidate_project_id"],
                text_similarity=c["text_similarity"],
                geographic_similarity=c["geographic_similarity"] if c["geographic_similarity"] is not None else 0.0,
                attribute_similarity=c["attribute_similarity"],
                combined_score=c["combined_score"],
                ui_label=c["ui_label"],
            ))

    risk_run.project_count = len(projects)
    risk_run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(risk_run)
    return risk_run
