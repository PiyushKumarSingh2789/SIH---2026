"""
Import pipeline core logic. Implements the canonical 4-step flow from the PRD:
upload -> map-columns -> preview/validate -> confirm.

Validation rules VAL-001..VAL-009 are exactly as specified in the PRD. One extra check
(STATUS_INVALID) is added beyond the PRD's numbered list because real CSVs will contain
free-text status values that don't match our enum -- documented here rather than silently
guessing, since guessing a status is exactly the kind of unexplained behavior the PRD
guardrails warn against ("missing fields must reduce analytics coverage, never silently
create low risk").
"""
import io
from datetime import date, datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.models import (
    Import, ImportRow, ImportValidationError, ImportStatus, ValidationSeverity,
    Project, Location, Agency, ProjectStatus, ProjectFinancial, ProjectProgress,
)

CANONICAL_FIELDS = [
    "project_code", "title", "description", "work_type", "state", "district",
    "constituency", "village_ward", "agency_name", "sanction_date", "recommendation_date",
    "expected_completion_date", "actual_completion_date", "sanctioned_amount", "estimated_cost",
    "utilized_amount", "physical_progress_percent", "status", "latitude", "longitude",
    "quantity", "unit_of_measure", "asset_status",
]

REQUIRED_FIELDS = [
    "project_code", "title", "work_type", "state", "district",
    "sanction_date", "sanctioned_amount", "status",
]

# Common header variations we auto-recognize (normalized: lowercase, spaces/underscores stripped)
_SYNONYMS = {
    "projectcode": "project_code", "code": "project_code",
    "projecttitle": "title", "name": "title",
    "worktype": "work_type", "category": "work_type",
    "sanctiondate": "sanction_date", "dateofsanction": "sanction_date",
    "sanctionedamount": "sanctioned_amount", "sanctionamount": "sanctioned_amount",
    "estimatedcost": "estimated_cost",
    "utilizedamount": "utilized_amount", "amountutilized": "utilized_amount",
    "physicalprogress": "physical_progress_percent", "progress": "physical_progress_percent",
    "progresspercent": "physical_progress_percent",
    "agencyname": "agency_name", "implementingagency": "agency_name",
    "expectedcompletiondate": "expected_completion_date",
    "actualcompletiondate": "actual_completion_date",
    "recommendationdate": "recommendation_date",
    "villageward": "village_ward", "lat": "latitude", "lon": "longitude", "lng": "longitude",
    "uom": "unit_of_measure", "assetstatus": "asset_status",
}


def _normalize_header(header: str) -> str:
    return header.strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def auto_detect_mapping(headers: list[str]) -> dict[str, str]:
    """Maps raw CSV headers -> canonical field names wherever confidently recognized.
    Headers that don't match anything are left unmapped (caller can map them manually)."""
    normalized_canonical = {_normalize_header(f): f for f in CANONICAL_FIELDS}
    mapping = {}
    for h in headers:
        norm = _normalize_header(h)
        if norm in normalized_canonical:
            mapping[h] = normalized_canonical[norm]
        elif norm in _SYNONYMS:
            mapping[h] = _SYNONYMS[norm]
    return mapping


def parse_uploaded_file(filename: str, content: bytes) -> pd.DataFrame:
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(content), dtype=str)
    return pd.read_csv(io.BytesIO(content), dtype=str)


def _get(row_raw: dict, mapping: dict[str, str], canonical_field: str):
    """Looks up a canonical field's value in a raw CSV row via the column_mapping."""
    for raw_col, canon in mapping.items():
        if canon == canonical_field:
            val = row_raw.get(raw_col)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            val = str(val).strip()
            return val if val else None
    return None


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(val: str | None) -> float | None:
    if val is None:
        return None
    try:
        return float(val.replace(",", ""))
    except ValueError:
        return None


def validate_import(db: Session, import_obj: Import) -> None:
    """Runs VAL-001..VAL-009 against every ImportRow, writes ImportValidationError rows,
    updates valid_rows/error_rows/status on the Import. Clears any previous validation
    errors first so re-running preview after re-mapping doesn't duplicate results."""
    db.query(ImportValidationError).filter(ImportValidationError.import_id == import_obj.id).delete()

    mapping = import_obj.column_mapping or {}
    rows = db.query(ImportRow).filter(ImportRow.import_id == import_obj.id).order_by(ImportRow.row_number).all()

    seen_codes_in_file: set[str] = set()
    valid_count = 0
    error_count = 0

    for row in rows:
        raw = row.raw_data
        errors: list[tuple[str, ValidationSeverity, str, str | None]] = []  # code, severity, message, field

        project_code = _get(raw, mapping, "project_code")
        title = _get(raw, mapping, "title")
        work_type = _get(raw, mapping, "work_type")
        state = _get(raw, mapping, "state")
        district = _get(raw, mapping, "district")
        sanction_date_raw = _get(raw, mapping, "sanction_date")
        sanctioned_amount_raw = _get(raw, mapping, "sanctioned_amount")
        estimated_cost_raw = _get(raw, mapping, "estimated_cost")
        status_raw = _get(raw, mapping, "status")
        progress_raw = _get(raw, mapping, "physical_progress_percent")
        lat_raw = _get(raw, mapping, "latitude")
        lon_raw = _get(raw, mapping, "longitude")
        expected_raw = _get(raw, mapping, "expected_completion_date")
        actual_raw = _get(raw, mapping, "actual_completion_date")
        utilized_raw = _get(raw, mapping, "utilized_amount")

        # Required fields present at all
        for field, val in [("project_code", project_code), ("title", title), ("work_type", work_type),
                            ("state", state), ("district", district), ("sanction_date", sanction_date_raw),
                            ("sanctioned_amount", sanctioned_amount_raw), ("status", status_raw)]:
            if not val:
                errors.append(("VAL-001" if field == "project_code" else "VAL-002",
                                ValidationSeverity.ERROR, f"Required field '{field}' is missing", field))

        # VAL-001: project_code unique in file and DB
        if project_code:
            if project_code in seen_codes_in_file:
                errors.append(("VAL-001", ValidationSeverity.ERROR,
                                f"Duplicate project_code '{project_code}' within the uploaded file", "project_code"))
            else:
                seen_codes_in_file.add(project_code)
                if db.query(Project).filter(Project.project_code == project_code).first():
                    errors.append(("VAL-001", ValidationSeverity.ERROR,
                                    f"project_code '{project_code}' already exists in the database", "project_code"))

        sanction_date = _parse_date(sanction_date_raw)
        if sanction_date_raw and not sanction_date:
            errors.append(("VAL-005", ValidationSeverity.ERROR, "sanction_date could not be parsed", "sanction_date"))

        sanctioned_amount = _parse_float(sanctioned_amount_raw)
        if sanctioned_amount_raw and sanctioned_amount is None:
            errors.append(("VAL-002", ValidationSeverity.ERROR, "sanctioned_amount is not a valid number", "sanctioned_amount"))
        elif sanctioned_amount is not None and sanctioned_amount < 0:
            errors.append(("VAL-002", ValidationSeverity.ERROR, "sanctioned_amount cannot be negative", "sanctioned_amount"))

        estimated_cost = _parse_float(estimated_cost_raw)
        if estimated_cost is not None and estimated_cost < 0:
            errors.append(("VAL-002", ValidationSeverity.ERROR, "estimated_cost cannot be negative", "estimated_cost"))

        # VAL-003: physical progress 0-100
        progress = _parse_float(progress_raw)
        if progress is not None and not (0 <= progress <= 100):
            errors.append(("VAL-003", ValidationSeverity.ERROR,
                            "physical_progress_percent must be between 0 and 100", "physical_progress_percent"))

        # VAL-004: coordinate bounds
        lat = _parse_float(lat_raw)
        lon = _parse_float(lon_raw)
        if lat is not None and not (-90 <= lat <= 90):
            errors.append(("VAL-004", ValidationSeverity.ERROR, "latitude must be between -90 and 90", "latitude"))
        if lon is not None and not (-180 <= lon <= 180):
            errors.append(("VAL-004", ValidationSeverity.ERROR, "longitude must be between -180 and 180", "longitude"))

        # VAL-005: expected/actual completion cannot precede sanction
        expected_date = _parse_date(expected_raw)
        actual_date = _parse_date(actual_raw)
        if sanction_date and expected_date and expected_date < sanction_date:
            errors.append(("VAL-005", ValidationSeverity.ERROR,
                            "expected_completion_date is before sanction_date", "expected_completion_date"))
        if sanction_date and actual_date and actual_date < sanction_date:
            errors.append(("VAL-005", ValidationSeverity.ERROR,
                            "actual_completion_date is before sanction_date", "actual_completion_date"))

        # VAL-006: utilized amount exceeds sanctioned amount (warning/signal, not blocking)
        utilized_amount = _parse_float(utilized_raw)
        if utilized_amount is not None and sanctioned_amount is not None and utilized_amount > sanctioned_amount:
            errors.append(("VAL-006", ValidationSeverity.WARNING,
                            "utilized_amount exceeds sanctioned_amount", "utilized_amount"))

        # Status parsing (extension beyond PRD's numbered list -- see module docstring)
        parsed_status = None
        if status_raw:
            normalized = status_raw.strip().lower().replace(" ", "_")
            if normalized in [s.value for s in ProjectStatus]:
                parsed_status = ProjectStatus(normalized)
            else:
                errors.append(("STATUS_INVALID", ValidationSeverity.WARNING,
                                f"Status '{status_raw}' not recognized, will default to 'sanctioned'", "status"))
                parsed_status = ProjectStatus.SANCTIONED

        # VAL-007: completed status but progress below 100
        if parsed_status == ProjectStatus.COMPLETED and progress is not None and progress < 100:
            errors.append(("VAL-007", ValidationSeverity.WARNING,
                            "Status is 'completed' but physical_progress_percent is below 100", "status"))

        # VAL-008: no valid coordinates
        if lat is None or lon is None:
            errors.append(("VAL-008", ValidationSeverity.WARNING,
                            "No valid coordinates provided -- geographic analysis unavailable for this project", None))

        # VAL-009: no payment/progress history in this upload
        if progress is None:
            errors.append(("VAL-009", ValidationSeverity.INFO,
                            "No progress data in this upload -- related risk factors will not be computed until added", None))

        has_blocking_error = any(sev == ValidationSeverity.ERROR for _, sev, _, _ in errors)
        row.is_valid = not has_blocking_error
        if has_blocking_error:
            error_count += 1
        else:
            valid_count += 1

        for code, severity, message, field in errors:
            db.add(ImportValidationError(
                import_id=import_obj.id, row_number=row.row_number,
                rule_code=code, severity=severity, message=message, field_name=field,
            ))

    import_obj.valid_rows = valid_count
    import_obj.error_rows = error_count
    import_obj.total_rows = len(rows)
    import_obj.status = ImportStatus.PREVIEWED
    db.commit()


def _get_or_create_location(db: Session, state: str, district: str,
                             village_ward: str | None, constituency: str | None,
                             lat: float | None, lon: float | None) -> Location:
    loc = db.query(Location).filter(Location.state == state, Location.district == district).first()
    if loc:
        return loc
    loc = Location(state=state, district=district, village_ward=village_ward,
                    constituency=constituency, latitude=lat, longitude=lon)
    db.add(loc)
    db.flush()
    return loc


def _get_or_create_agency(db: Session, name: str | None) -> Agency | None:
    if not name:
        return None
    agency = db.query(Agency).filter(Agency.name == name).first()
    if agency:
        return agency
    agency = Agency(name=name)
    db.add(agency)
    db.flush()
    return agency


def confirm_import(db: Session, import_obj: Import) -> int:
    """Persists every valid row (VAL-001..005 all clear -- warnings/info don't block) as a Project,
    plus its ProjectFinancial/ProjectProgress rows when the source data provided those values.
    Safe to call only after preview has run. Wrapped in a single transaction -- if any row fails,
    the whole confirm rolls back rather than leaving a partially-imported batch."""
    mapping = import_obj.column_mapping or {}
    rows = (
        db.query(ImportRow)
        .filter(ImportRow.import_id == import_obj.id, ImportRow.is_valid == True)  # noqa: E712
        .order_by(ImportRow.row_number).all()
    )

    created = 0
    try:
        for row in rows:
            raw = row.raw_data
            state = _get(raw, mapping, "state")
            district = _get(raw, mapping, "district")
            lat = _parse_float(_get(raw, mapping, "latitude"))
            lon = _parse_float(_get(raw, mapping, "longitude"))
            location = _get_or_create_location(
                db, state, district, _get(raw, mapping, "village_ward"),
                _get(raw, mapping, "constituency"), lat, lon,
            )
            agency = _get_or_create_agency(db, _get(raw, mapping, "agency_name"))

            status_raw = _get(raw, mapping, "status")
            normalized = (status_raw or "").strip().lower().replace(" ", "_")
            status = ProjectStatus(normalized) if normalized in [s.value for s in ProjectStatus] else ProjectStatus.SANCTIONED

            sanctioned_amount = _parse_float(_get(raw, mapping, "sanctioned_amount")) or 0
            estimated_cost = _parse_float(_get(raw, mapping, "estimated_cost"))
            sanction_date = _parse_date(_get(raw, mapping, "sanction_date"))

            project = Project(
                project_code=_get(raw, mapping, "project_code"),
                title=_get(raw, mapping, "title"),
                description=_get(raw, mapping, "description"),
                work_type=_get(raw, mapping, "work_type"),
                status=status,
                agency_id=agency.id if agency else None,
                location_id=location.id,
                recommendation_date=_parse_date(_get(raw, mapping, "recommendation_date")),
                sanction_date=sanction_date,
                expected_completion_date=_parse_date(_get(raw, mapping, "expected_completion_date")),
                actual_completion_date=_parse_date(_get(raw, mapping, "actual_completion_date")),
                sanctioned_amount=sanctioned_amount,
                estimated_cost=estimated_cost,
                unit_of_measure=_get(raw, mapping, "unit_of_measure"),
                asset_status=_get(raw, mapping, "asset_status"),
            )
            db.add(project)
            db.flush()
            row.resulting_project_id = project.id
            created += 1

            # Phase 12 fix: imported utilization/progress values must actually reach the risk engine.
            # Without these, every imported project would permanently show factors_computed_count=0
            # for PROGRESS_EXPENDITURE_MISMATCH and DELAY_STALL -- silently incomplete, not just "new".
            # Only create a row when the source data actually provided a value (never fabricate).
            utilized_amount = _parse_float(_get(raw, mapping, "utilized_amount"))
            if utilized_amount is not None:
                db.add(ProjectFinancial(project_id=project.id, utilized_amount=utilized_amount, as_of_date=date.today()))

            progress_pct = _parse_float(_get(raw, mapping, "physical_progress_percent"))
            if progress_pct is not None:
                db.add(ProjectProgress(project_id=project.id, report_date=date.today(), physical_progress_percent=progress_pct))

        import_obj.status = ImportStatus.CONFIRMED
        db.commit()
        return created
    except Exception:
        db.rollback()
        raise
