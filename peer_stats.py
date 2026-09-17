"""
Peer group computation. Fallback hierarchy per PRD Section 6:
1. work_type + district + sanction_year
2. work_type + state + sanction_year
3. work_type + state
4. work_type + national
A group is only used once it has >= MIN_SAMPLE_SIZE comparable projects.
"""
import statistics
from dataclasses import dataclass
from datetime import date

import numpy as np
from sqlalchemy.orm import Session

from app.models import Project, Location

MIN_SAMPLE_SIZE = 10


@dataclass
class PeerStats:
    median_cost: float
    iqr_low: float
    iqr_high: float
    sample_count: int
    group_level: str   # "district" / "state" / "national"
    group_value: str | None


def _costs_for(db: Session, work_type: str, state: str | None = None,
                district: str | None = None, sanction_year: int | None = None) -> list[float]:
    q = db.query(Project.sanctioned_amount).join(Location, Project.location_id == Location.id).filter(
        Project.work_type == work_type
    )
    if state:
        q = q.filter(Location.state == state)
    if district:
        q = q.filter(Location.district == district)
    if sanction_year:
        q = q.filter(Project.sanction_date >= date(sanction_year, 1, 1),
                      Project.sanction_date <= date(sanction_year, 12, 31))
    return [float(v[0]) for v in q.all()]


def compute_peer_stats(db: Session, work_type: str, state: str | None, district: str | None,
                        sanction_year: int | None) -> PeerStats | None:
    """Returns None if even the national fallback doesn't have enough samples -- caller must
    skip the cost-deviation factor entirely in that case (never fabricate a peer group)."""

    candidates = [
        ("district", district, {"state": state, "district": district, "sanction_year": sanction_year}),
        ("state", state, {"state": state, "sanction_year": sanction_year}),
        ("state", state, {"state": state}),
        ("national", None, {}),
    ]

    for level, value, filters in candidates:
        if level != "national" and not value:
            continue
        costs = _costs_for(db, work_type, **filters)
        if len(costs) >= MIN_SAMPLE_SIZE:
            median = statistics.median(costs)
            q1, q3 = np.percentile(costs, [25, 75])
            return PeerStats(
                median_cost=median, iqr_low=float(q1), iqr_high=float(q3),
                sample_count=len(costs), group_level=level, group_value=value,
            )
    return None
