"""
Deterministic synthetic data generator for SIH26102.
Run: python -m app.seeds.generate_synthetic_data

Produces ~1,500 project records with realistic progress/payment history, plus ~96 engineered
"hero" anomaly cases (12 per category x 8 categories) so every detector in the Risk Engine has
at least one clear, visible example to point to during the demo.

Fixed random.seed(42) -> re-running against a fresh DB produces identical data every time.
No hero-case flag is stored anywhere in the schema on purpose: the platform must find these
through the actual detectors, not through a shortcut column (see PRD guardrail: never hard-code
unexplained risk values). A manifest of which project_codes are hero cases is written separately,
for YOUR testing reference only -- never expose that file to the app or the demo.
"""
import json
import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.models import (
    Base, Agency, Location, Project, ProjectFinancial, ProjectProgress, Payment, ProjectStatus,
)
from app.seeds.reference_data import (
    STATE_DISTRICTS, STATE_BOUNDS, WORK_TYPES, WORK_TYPE_BASE_COST, build_agency_names,
    TITLE_DESCRIPTORS, DESCRIPTION_SCOPE_PHRASES, DESCRIPTION_BENEFICIARY_PHRASES,
)

random.seed(42)

TOTAL_PROJECTS = 1500
HERO_CATEGORIES = [
    "cost_outlier", "progress_expenditure_mismatch", "stall", "late_completion",
    "duplicate_pair", "payment_anomaly", "data_quality_issue", "connected_pattern",
]
PER_HERO_CATEGORY = 12  # 12 x 8 = 96, within the PRD's 75-120 hero case target
NORMAL_PROJECT_COUNT = TOTAL_PROJECTS - (PER_HERO_CATEGORY * len(HERO_CATEGORIES))

TODAY = date(2026, 9, 9)  # fixed "as of" date so re-runs are fully reproducible

_code_counter = {"n": 0}


def next_project_code() -> str:
    _code_counter["n"] += 1
    return f"PRJ-2026-{_code_counter['n']:05d}"


def random_date(start: date, end: date) -> date:
    if end <= start:
        return start
    return start + timedelta(days=random.randint(0, (end - start).days))


def jitter_location(state: str) -> tuple[float, float]:
    lat_min, lon_min, lat_max, lon_max = STATE_BOUNDS[state]
    return round(random.uniform(lat_min, lat_max), 6), round(random.uniform(lon_min, lon_max), 6)


def seed_locations(db: Session) -> list[Location]:
    locations = []
    for state, districts in STATE_DISTRICTS.items():
        for district in districts:
            lat, lon = jitter_location(state)
            loc = Location(state=state, district=district, latitude=lat, longitude=lon)
            db.add(loc)
            locations.append(loc)
    db.flush()
    return locations


def seed_agencies(db: Session) -> list[Agency]:
    agencies = [Agency(name=name, agency_type="Government") for name in build_agency_names()]
    db.add_all(agencies)
    db.flush()
    return agencies


def project_specific_location(db: Session, base_location: Location) -> Location:
    """Creates a NEW Location row for this one project, jittered a few km around the district's
    base coordinates (same state/district text, so peer-group filtering by district is unaffected).

    Without this, every project in the same district shared the exact same Location row and thus
    identical coordinates -- which made the DUPLICATE_SIMILARITY detector's geographic term read
    100% similarity for any two same-district projects regardless of whether they were actually
    related, producing large numbers of false-positive duplicate candidates. This was found during
    testing: baseline (non-hero) projects were averaging ~92/100 on DUPLICATE_SIMILARITY, when they
    should have been near 0."""
    if base_location.latitude is None or base_location.longitude is None:
        loc = Location(state=base_location.state, district=base_location.district,
                        village_ward=base_location.village_ward, constituency=base_location.constituency,
                        latitude=None, longitude=None)
    else:
        # ~0.01 deg latitude =~ 1.1km. Jitter of +/-0.15 deg (~15-16km) ensures two independently
        # jittered same-district projects overwhelmingly land beyond GEO_ZERO_KM (5km) apart by
        # chance, while the deliberately-engineered duplicate_pair hero case (which reuses the
        # exact same un-jittered Location) stays clearly distinguishable at 0km apart. A smaller
        # jitter (originally +/-0.03, ~3km) was tried first and wasn't enough -- most same-district
        # pairs still coincidentally landed inside the 5km zero-similarity band.
        loc = Location(state=base_location.state, district=base_location.district,
                        village_ward=base_location.village_ward, constituency=base_location.constituency,
                        latitude=round(base_location.latitude + random.uniform(-0.15, 0.15), 6),
                        longitude=round(base_location.longitude + random.uniform(-0.15, 0.15), 6))
    db.add(loc)
    db.flush()
    return loc


def peer_cost(work_type: str) -> float:
    base = WORK_TYPE_BASE_COST[work_type]
    return max(base * random.lognormvariate(0, 0.18), base * 0.5)


def add_progress_and_payments(db: Session, project: Project, sanction: date, expected: date,
                               final_progress: float, final_utilization_ratio: float,
                               num_progress: int, num_payments: int, stalled: bool = False,
                               skip_history: bool = False) -> None:
    """Builds a progress+payment trail that lands on the given final numbers.
    skip_history=True deliberately produces VAL-009 (no payment/progress history) for data-issue heroes."""
    if skip_history:
        return

    report_dates = sorted(random_date(sanction, min(TODAY, expected)) for _ in range(num_progress))
    if stalled and len(report_dates) >= 2:
        # Force the last two reports into a genuine ~50-day flat window ending recently, so the
        # DELAY_STALL detector's "last 60 days" check actually has qualifying data to look at.
        # Without this, purely random dates across the whole project timeline could land the
        # "flat" reports anywhere -- including years before the as-of date -- and the detector
        # would correctly find nothing to flag (which is NOT what a stall hero case should do).
        report_dates[-2] = TODAY - timedelta(days=55)
        report_dates[-1] = TODAY - timedelta(days=5)
        report_dates = sorted(report_dates)
    for i, rdate in enumerate(report_dates):
        if stalled and i >= max(num_progress - 2, 0):
            pct = final_progress  # flat last two reports -> stall signature (DELAY_STALL detector)
        else:
            pct = round(final_progress * (i + 1) / num_progress * random.uniform(0.85, 1.0), 1)
        db.add(ProjectProgress(project_id=project.id, report_date=rdate,
                                physical_progress_percent=round(min(pct, 100.0), 1)))

    utilized_total = Decimal(str(round(float(project.sanctioned_amount) * final_utilization_ratio, 2)))
    db.add(ProjectFinancial(project_id=project.id, utilized_amount=utilized_total, as_of_date=TODAY))

    if num_payments > 0:
        remaining = utilized_total
        pay_dates = sorted(random_date(sanction, TODAY) for _ in range(num_payments))
        for i, pdate in enumerate(pay_dates):
            if i == num_payments - 1:
                amt = remaining
            else:
                share = (remaining / (num_payments - i)) * Decimal(str(round(random.uniform(0.6, 1.4), 2)))
                amt = min(share, remaining) if remaining > 0 else Decimal("0")
            remaining -= amt
            db.add(Payment(project_id=project.id, payment_date=pdate,
                            payment_amount=round(max(amt, Decimal("0")), 2), payment_type="milestone"))


def make_random_description(work_type: str, district: str, state: str) -> str:
    scope = random.choice(DESCRIPTION_SCOPE_PHRASES).format(n=random.choice([150, 220, 300, 450, 600, 800]))
    beneficiary = random.choice(DESCRIPTION_BENEFICIARY_PHRASES)
    return f"{work_type} project under MPLADS in {district}, {state}, {scope}. {beneficiary}"


def make_base_project(work_type: str, location: Location, agency: Agency, cost_multiplier: float = 1.0,
                       title_suffix: str = "") -> tuple[Project, date, date]:
    sanction = random_date(date(2023, 4, 1), date(2026, 6, 1))
    duration_days = random.randint(180, 730)
    expected = sanction + timedelta(days=duration_days)
    cost = round(peer_cost(work_type) * cost_multiplier, 2)

    title = f"{work_type} at {location.village_ward or location.district}, {random.choice(TITLE_DESCRIPTORS)}{title_suffix}"
    project = Project(
        project_code=next_project_code(),
        title=title,
        description=make_random_description(work_type, location.district, location.state),
        work_type=work_type,
        status=ProjectStatus.IN_PROGRESS,
        agency_id=agency.id,
        location_id=location.id,
        sanction_date=sanction,
        expected_completion_date=expected,
        sanctioned_amount=Decimal(str(cost)),
        estimated_cost=Decimal(str(round(cost * random.uniform(0.95, 1.05), 2))),
    )
    return project, sanction, expected


def generate_normal_projects(db: Session, locations: list[Location], agencies: list[Agency]) -> None:
    for _ in range(NORMAL_PROJECT_COUNT):
        work_type = random.choice(WORK_TYPES)
        location = project_specific_location(db, random.choice(locations))
        agency = random.choice(agencies)
        project, sanction, expected = make_base_project(work_type, location, agency)

        elapsed_ratio = min(1.0, (TODAY - sanction).days / max((expected - sanction).days, 1))
        final_progress = round(min(100, elapsed_ratio * 100 * random.uniform(0.75, 1.05)), 1)
        final_utilization_ratio = round(min(1.0, final_progress / 100 * random.uniform(0.85, 1.1)), 3)

        if final_progress >= 99.5 and random.random() < 0.7:
            project.status = ProjectStatus.COMPLETED
            project.actual_completion_date = expected - timedelta(days=random.randint(-20, 20))
        elif elapsed_ratio < 0.05:
            project.status = ProjectStatus.SANCTIONED

        db.add(project)
        db.flush()
        add_progress_and_payments(
            db, project, sanction, expected, final_progress, final_utilization_ratio,
            num_progress=random.randint(3, 8), num_payments=random.randint(1, 6),
        )


def generate_hero_cases(db: Session, locations: list[Location], agencies: list[Agency]) -> list[dict]:
    manifest = []

    # 1. COST_OUTLIER -- cost 2.5-4x the peer median for its work type
    for _ in range(PER_HERO_CATEGORY):
        work_type = random.choice(WORK_TYPES)
        location = project_specific_location(db, random.choice(locations))
        agency = random.choice(agencies)
        project, sanction, expected = make_base_project(work_type, location, agency,
                                                          cost_multiplier=random.uniform(2.5, 4.0))
        db.add(project)
        db.flush()
        add_progress_and_payments(db, project, sanction, expected, final_progress=60.0,
                                   final_utilization_ratio=0.55, num_progress=4, num_payments=3)
        manifest.append({"project_code": project.project_code, "category": "cost_outlier"})

    # 2. PROGRESS_EXPENDITURE_MISMATCH -- high utilization, low physical progress
    for _ in range(PER_HERO_CATEGORY):
        work_type = random.choice(WORK_TYPES)
        location = project_specific_location(db, random.choice(locations))
        agency = random.choice(agencies)
        project, sanction, expected = make_base_project(work_type, location, agency)
        db.add(project)
        db.flush()
        add_progress_and_payments(db, project, sanction, expected, final_progress=random.uniform(10, 20),
                                   final_utilization_ratio=random.uniform(0.80, 0.95),
                                   num_progress=4, num_payments=5)
        manifest.append({"project_code": project.project_code, "category": "progress_expenditure_mismatch"})

    # 3. STALL -- flat progress for the last 60+ days, status still in_progress
    for _ in range(PER_HERO_CATEGORY):
        work_type = random.choice(WORK_TYPES)
        location = project_specific_location(db, random.choice(locations))
        agency = random.choice(agencies)
        project, sanction, expected = make_base_project(work_type, location, agency)
        project.expected_completion_date = TODAY + timedelta(days=random.randint(60, 200))  # not yet overdue
        db.add(project)
        db.flush()
        add_progress_and_payments(db, project, sanction, expected, final_progress=random.uniform(30, 50),
                                   final_utilization_ratio=random.uniform(0.35, 0.55),
                                   num_progress=5, num_payments=3, stalled=True)
        manifest.append({"project_code": project.project_code, "category": "stall"})

    # 4. LATE_COMPLETION -- expected date already passed, not completed, meaningful progress lag
    for _ in range(PER_HERO_CATEGORY):
        work_type = random.choice(WORK_TYPES)
        location = project_specific_location(db, random.choice(locations))
        agency = random.choice(agencies)
        project, sanction, expected = make_base_project(work_type, location, agency)
        project.expected_completion_date = TODAY - timedelta(days=random.randint(30, 200))  # already overdue
        db.add(project)
        db.flush()
        add_progress_and_payments(db, project, sanction, project.expected_completion_date,
                                   final_progress=random.uniform(40, 65),
                                   final_utilization_ratio=random.uniform(0.45, 0.65),
                                   num_progress=5, num_payments=4)
        manifest.append({"project_code": project.project_code, "category": "late_completion"})

    # 5. DUPLICATE_PAIR -- two near-identical projects, same location, similar cost/title
    for _ in range(PER_HERO_CATEGORY):
        work_type = random.choice(WORK_TYPES)
        location = random.choice(locations)
        agency_a = random.choice(agencies)
        agency_b = random.choice(agencies)
        base_cost_mult = random.uniform(0.95, 1.05)
        p1, s1, e1 = make_base_project(work_type, location, agency_a, cost_multiplier=1.0)
        p2, s2, e2 = make_base_project(work_type, location, agency_b, cost_multiplier=base_cost_mult,
                                        title_suffix=" (Phase Extension)")
        p2.title = p1.title  # force near-identical text for TF-IDF similarity
        p2.description = p1.description  # same -- a real duplicate submission would reuse wording too
        db.add_all([p1, p2])
        db.flush()
        for p, s, e in [(p1, s1, e1), (p2, s2, e2)]:
            add_progress_and_payments(db, p, s, e, final_progress=random.uniform(20, 60),
                                       final_utilization_ratio=random.uniform(0.3, 0.6),
                                       num_progress=3, num_payments=2)
        manifest.append({"project_code": p1.project_code, "pair_with": p2.project_code, "category": "duplicate_pair"})

    # 6. PAYMENT_ANOMALY -- a payment dated before the sanction date (also trips CMP-005)
    for _ in range(PER_HERO_CATEGORY):
        work_type = random.choice(WORK_TYPES)
        location = project_specific_location(db, random.choice(locations))
        agency = random.choice(agencies)
        project, sanction, expected = make_base_project(work_type, location, agency)
        db.add(project)
        db.flush()
        add_progress_and_payments(db, project, sanction, expected, final_progress=random.uniform(30, 60),
                                   final_utilization_ratio=random.uniform(0.4, 0.7),
                                   num_progress=4, num_payments=3)
        db.add(Payment(project_id=project.id, payment_date=sanction - timedelta(days=random.randint(5, 40)),
                        payment_amount=Decimal(str(round(float(project.sanctioned_amount) * 0.15, 2))),
                        payment_type="advance_irregular"))
        manifest.append({"project_code": project.project_code, "category": "payment_anomaly"})

    # 7. DATA_QUALITY_ISSUE -- missing coordinates (VAL-008) and no progress/payment history (VAL-009)
    for _ in range(PER_HERO_CATEGORY):
        work_type = random.choice(WORK_TYPES)
        state = random.choice(list(STATE_DISTRICTS.keys()))
        district = random.choice(STATE_DISTRICTS[state])
        no_coord_location = Location(state=state, district=district, latitude=None, longitude=None)
        db.add(no_coord_location)
        db.flush()
        agency = random.choice(agencies)
        project, sanction, expected = make_base_project(work_type, no_coord_location, agency)
        db.add(project)
        db.flush()
        add_progress_and_payments(db, project, sanction, expected, final_progress=0, final_utilization_ratio=0,
                                   num_progress=0, num_payments=0, skip_history=True)
        manifest.append({"project_code": project.project_code, "category": "data_quality_issue"})

    # 8. CONNECTED_PATTERN -- a cluster of 5 projects under ONE agency, all mildly cost-anomalous
    #    (relationship intelligence should surface this cluster as a connected risk pattern, P1 feature)
    for cluster_idx in range(PER_HERO_CATEGORY // 4):  # 3 clusters of ~4 projects each ~ still near 12 total
        agency = random.choice(agencies)
        for _ in range(4):
            work_type = random.choice(WORK_TYPES)
            location = project_specific_location(db, random.choice(locations))
            project, sanction, expected = make_base_project(work_type, location, agency,
                                                              cost_multiplier=random.uniform(1.6, 2.0))
            db.add(project)
            db.flush()
            add_progress_and_payments(db, project, sanction, expected, final_progress=random.uniform(25, 45),
                                       final_utilization_ratio=random.uniform(0.5, 0.7),
                                       num_progress=3, num_payments=3)
            manifest.append({"project_code": project.project_code, "category": "connected_pattern",
                              "cluster": f"agency_{agency.id[:8]}"})

    return manifest


def run(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        locations = seed_locations(db)
        agencies = seed_agencies(db)
        generate_normal_projects(db, locations, agencies)
        manifest = generate_hero_cases(db, locations, agencies)
        db.commit()

        with open("seed_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        print(f"Seeded {TOTAL_PROJECTS} projects total "
              f"({NORMAL_PROJECT_COUNT} normal + {len(manifest)} hero cases across "
              f"{len(HERO_CATEGORIES)} categories).")
        print("Hero case manifest written to seed_manifest.json (for YOUR testing reference only "
              "-- do not expose this file in the app or demo).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    run(reset="--reset" in sys.argv)
