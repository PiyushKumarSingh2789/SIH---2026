"""
Shared per-project feature engineering used by the batch-level detectors
(PEER_DEVIATION, ML_ANOMALY, DUPLICATE_SIMILARITY). Built once per risk run
from bulk-loaded project data so all three detectors share one consistent
feature set instead of each re-deriving it a different way.

Implements the PRD Section 5 "Core formulas" verbatim:
  Utilization Ratio = utilized_amount / max(sanctioned_amount, 1)
  Elapsed Ratio = (as_of_date - sanction_date) / max(expected_completion_date - sanction_date, 1)
  Expected Progress % = min(100, elapsed_ratio * 100)
  Progress Lag = max(0, expected_progress_percent - physical_progress_percent)
  Progress-Expenditure Gap = |utilization_ratio*100 - physical_progress_percent|
"""
from datetime import date


def build_feature_row(project, location, agency, latest_financial, latest_progress,
                       payments: list, as_of: date) -> dict:
    sanctioned_amount = float(project.sanctioned_amount)
    utilized_amount = float(latest_financial.utilized_amount) if latest_financial else 0.0
    utilization_ratio = utilized_amount / max(sanctioned_amount, 1)
    physical_progress_percent = latest_progress.physical_progress_percent if latest_progress else 0.0

    elapsed_days = (as_of - project.sanction_date).days if project.sanction_date else None

    duration_days = None
    expected_progress_percent = None
    progress_lag = None
    if project.sanction_date and project.expected_completion_date:
        duration_days = (project.expected_completion_date - project.sanction_date).days
        elapsed_ratio = (elapsed_days or 0) / max(duration_days, 1)
        expected_progress_percent = min(100.0, elapsed_ratio * 100)
        progress_lag = max(0.0, expected_progress_percent - physical_progress_percent)

    progress_expenditure_gap = abs(utilization_ratio * 100 - physical_progress_percent)

    payments_sorted = sorted(payments, key=lambda p: p.payment_date) if payments else []
    payment_count = len(payments_sorted)
    payment_amount_total = float(sum(p.payment_amount for p in payments_sorted)) if payments_sorted else 0.0
    payment_interval_avg_days = None
    if payment_count >= 2:
        gaps = [
            (payments_sorted[i].payment_date - payments_sorted[i - 1].payment_date).days
            for i in range(1, payment_count)
        ]
        payment_interval_avg_days = sum(gaps) / len(gaps)

    return {
        "project_id": project.id,
        "project_code": project.project_code,
        "title": project.title,
        "description": project.description,
        "work_type": project.work_type,
        "agency_name": agency.name if agency else None,
        "state": location.state if location else None,
        "district": location.district if location else None,
        "latitude": location.latitude if location else None,
        "longitude": location.longitude if location else None,
        "sanction_date": project.sanction_date,
        "sanction_year": project.sanction_date.year if project.sanction_date else None,
        "sanctioned_amount": sanctioned_amount,
        "utilized_amount": utilized_amount,
        "utilization_ratio": utilization_ratio,
        "physical_progress_percent": physical_progress_percent,
        "elapsed_days": elapsed_days,
        "duration_days": duration_days,
        "expected_progress_percent": expected_progress_percent,
        "progress_lag": progress_lag,
        "progress_expenditure_gap": progress_expenditure_gap,
        "cost_deviation_percent": None,  # filled in by risk_engine after COST_DEVIATION runs
        "peer_deviation_score": None,    # filled in by risk_engine after PEER_DEVIATION runs
        "payment_count": payment_count,
        "payment_amount_total": payment_amount_total,
        "payment_interval_avg_days": payment_interval_avg_days,
        "status": project.status.value if project.status else None,
        "actual_completion_date": project.actual_completion_date,
    }
