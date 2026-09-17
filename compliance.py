"""
Computes the PRD's CMP-00x compliance checks LIVE from existing Project/Payment/Financial/
Progress data -- deliberately NOT writing to the existing (but currently unpopulated)
ComplianceCheck table. Nothing in the risk engine or anywhere else ever computes these checks
today, so retrofitting risk_engine.py to persist them is a bigger change than this pass calls
for; these are cheap boolean/comparison checks over data already loaded, safe to compute on
every request.

Only implements the checks answerable from fields that actually exist on Project/Payment/
ProjectFinancial/ProjectProgress -- CMP checks that would need data the schema doesn't carry
(e.g. checks against an external sanction-order document) are not fabricated here.
"""
from datetime import date


def evaluate_compliance(project, latest_financial, latest_progress, payments: list) -> list[dict]:
    results = []

    if project.estimated_cost:
        tolerance_amount = float(project.estimated_cost) * 1.1
        if float(project.sanctioned_amount) > tolerance_amount:
            results.append({
                "check_code": "CMP-001", "result": "WARNING",
                "evidence": {
                    "sanctioned_amount": float(project.sanctioned_amount),
                    "estimated_cost": float(project.estimated_cost),
                    "tolerance_percent": 10,
                },
            })
        else:
            results.append({"check_code": "CMP-001", "result": "PASS", "evidence": {}})

    if latest_financial:
        if float(latest_financial.utilized_amount) > float(project.sanctioned_amount):
            results.append({
                "check_code": "CMP-002", "result": "FAIL",
                "evidence": {
                    "utilized_amount": float(latest_financial.utilized_amount),
                    "sanctioned_amount": float(project.sanctioned_amount),
                },
            })
        else:
            results.append({"check_code": "CMP-002", "result": "PASS", "evidence": {}})

    if project.expected_completion_date:
        if project.expected_completion_date < project.sanction_date:
            results.append({
                "check_code": "CMP-003", "result": "FAIL",
                "evidence": {
                    "expected_completion_date": project.expected_completion_date.isoformat(),
                    "sanction_date": project.sanction_date.isoformat(),
                },
            })
        else:
            results.append({"check_code": "CMP-003", "result": "PASS", "evidence": {}})

    if project.actual_completion_date:
        if project.actual_completion_date < project.sanction_date:
            results.append({
                "check_code": "CMP-004", "result": "FAIL",
                "evidence": {
                    "actual_completion_date": project.actual_completion_date.isoformat(),
                    "sanction_date": project.sanction_date.isoformat(),
                },
            })
        else:
            results.append({"check_code": "CMP-004", "result": "PASS", "evidence": {}})

    if payments:
        pre_sanction = [p for p in payments if p.payment_date < project.sanction_date]
        if pre_sanction:
            results.append({
                "check_code": "CMP-005", "result": "FAIL",
                "evidence": {
                    "pre_sanction_payment_count": len(pre_sanction),
                    "earliest_payment_date": min(p.payment_date for p in pre_sanction).isoformat(),
                    "sanction_date": project.sanction_date.isoformat(),
                },
            })
        else:
            results.append({"check_code": "CMP-005", "result": "PASS", "evidence": {}})

    if project.status.value == "completed":
        progress = latest_progress.physical_progress_percent if latest_progress else 0
        if progress < 100:
            results.append({
                "check_code": "CMP-006", "result": "WARNING",
                "evidence": {"status": "completed", "physical_progress_percent": progress},
            })
        else:
            results.append({"check_code": "CMP-006", "result": "PASS", "evidence": {}})

    if project.location_id is None or not project.location or project.location.latitude is None or project.location.longitude is None:
        results.append({"check_code": "CMP-007", "result": "WARNING", "evidence": {"has_coordinates": False}})
    else:
        results.append({"check_code": "CMP-007", "result": "PASS", "evidence": {}})

    return results
