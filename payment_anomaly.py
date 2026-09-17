"""
PAYMENT_ANOMALY detector. Weight: 15%.
Rule-based chronology/amount checks plus a payments-vs-recorded-utilization
consistency check. Skipped entirely if the project has no payment history
(PRD: "skip when payment history absent").
"""
from datetime import date


def compute_payment_anomaly(
    payments: list, sanction_date: date, actual_completion_date: date | None,
    is_completed: bool, sanctioned_amount: float, utilized_amount: float,
) -> dict | None:
    if not payments:
        return None

    score = 0.0
    flags: list[str] = []

    pre_sanction = [p for p in payments if p.payment_date < sanction_date]
    if pre_sanction:
        score += 50
        flags.append(
            f"{len(pre_sanction)} payment(s) dated before the project's sanction date "
            f"({sanction_date.isoformat()})"
        )

    post_completion = []
    if is_completed and actual_completion_date:
        post_completion = [p for p in payments if p.payment_date > actual_completion_date]
        if post_completion:
            score += 25
            flags.append(
                f"{len(post_completion)} payment(s) dated after the recorded completion date "
                f"({actual_completion_date.isoformat()})"
            )

    max_payment = max(float(p.payment_amount) for p in payments)
    max_ratio = max_payment / max(sanctioned_amount, 1)
    if max_ratio > 0.5:
        score += min(25.0, (max_ratio - 0.5) * 50 + 15)
        flags.append(
            f"a single payment of Rs {max_payment:,.0f} equals {max_ratio * 100:.0f}% "
            f"of the sanctioned amount"
        )

    payments_total = float(sum(p.payment_amount for p in payments))
    discrepancy_percent = abs(payments_total - utilized_amount) / max(utilized_amount, 1) * 100
    if discrepancy_percent > 15:
        score += 20
        flags.append(
            f"recorded payments total (Rs {payments_total:,.0f}) differs from reported "
            f"utilization (Rs {utilized_amount:,.0f}) by {discrepancy_percent:.0f}%"
        )

    normalized_score = min(100.0, score)

    if flags:
        explanation = "Payment review found: " + "; ".join(flags) + "."
    else:
        explanation = (
            f"{len(payments)} payment(s) reviewed for chronology and amount consistency -- "
            f"no irregularities found."
        )

    evidence = {
        "payment_count": len(payments),
        "payments_total": round(payments_total, 2),
        "utilized_amount": round(utilized_amount, 2),
        "sanctioned_amount": round(sanctioned_amount, 2),
        "pre_sanction_payment_count": len(pre_sanction),
        "post_completion_payment_count": len(post_completion),
        "max_single_payment_ratio": round(max_ratio, 3),
        "payments_vs_utilized_discrepancy_percent": round(discrepancy_percent, 1),
    }
    return {
        "raw_value": round(score, 2),
        "normalized_score": round(normalized_score, 2),
        "evidence": evidence,
        "explanation": explanation,
    }
