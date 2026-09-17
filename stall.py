"""
DELAY_STALL detector. Weight: 15%.
Per PRD: "less than 2 percentage points of progress over 60 days with at least two reports
and non-completed status." Skipped if there isn't enough report history to judge a 60-day window.
"""
from datetime import date


def compute_stall(progress_reports: list[tuple[date, float]], as_of: date, is_completed: bool) -> dict | None:
    if is_completed or len(progress_reports) < 2:
        return None

    window_start = as_of.toordinal() - 60
    recent = sorted(
        [(d, p) for d, p in progress_reports if d.toordinal() >= window_start],
        key=lambda x: x[0],
    )
    if len(recent) < 2:
        return None

    span_days = (recent[-1][0] - recent[0][0]).days
    if span_days < 45:  # not enough of a 60-day window observed yet -- don't guess
        return None

    change = recent[-1][1] - recent[0][1]
    normalized_score = min(100.0, max(0.0, 100.0 - change * 20.0))

    stalled = change < 2.0
    explanation = (
        f"Physical progress moved only {change:.1f} percentage points over the last {span_days} days "
        f"({'flagged as stalled' if stalled else 'within normal range'})."
    )
    evidence = {
        "progress_change": round(change, 2),
        "window_days": span_days,
        "report_count_in_window": len(recent),
        "stalled": stalled,
    }
    return {
        "raw_value": round(change, 2),
        "normalized_score": round(normalized_score, 2),
        "evidence": evidence,
        "explanation": explanation,
    }
