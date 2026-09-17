"""
PROGRESS_EXPENDITURE_MISMATCH detector. Weight: 20%.
Skipped if the project has no ProjectFinancial row (no utilization data) or no progress reports.
"""


def compute_mismatch(utilized_amount: float, sanctioned_amount: float, physical_progress_percent: float) -> dict:
    utilization_ratio = utilized_amount / max(sanctioned_amount, 1)
    gap = abs(utilization_ratio * 100 - physical_progress_percent)
    normalized_score = min(100.0, gap)

    direction = "higher than" if utilization_ratio * 100 > physical_progress_percent else "lower than"
    explanation = (
        f"Financial utilization ({utilization_ratio * 100:.1f}%) is {direction} physical progress "
        f"({physical_progress_percent:.1f}%) by {gap:.1f} percentage points."
    )
    evidence = {
        "utilization_percent": round(utilization_ratio * 100, 2),
        "physical_progress_percent": round(physical_progress_percent, 2),
        "gap_percentage_points": round(gap, 2),
    }
    return {
        "raw_value": round(gap, 2),
        "normalized_score": round(normalized_score, 2),
        "evidence": evidence,
        "explanation": explanation,
    }
