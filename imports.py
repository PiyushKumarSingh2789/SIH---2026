from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.models import Import, ImportRow, ImportValidationError, ImportStatus, User, RoleName
from app.schemas.imports import (
    ImportOut, MapColumnsRequest, PreviewResponse, PreviewRowOut, ValidationErrorOut, ConfirmResponse,
)
from app.services.import_service import auto_detect_mapping, parse_uploaded_file, validate_import, confirm_import

router = APIRouter(prefix="/imports", tags=["imports"])

# Only admin roles can import data -- this creates/modifies projects platform-wide.
_import_roles = require_roles(RoleName.SYSTEM_ADMIN, RoleName.MINISTRY_ADMIN)


@router.post("/upload", response_model=ImportOut)
def upload_import(
    file: UploadFile = File(...),
    current_user: User = Depends(_import_roles),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only .csv, .xlsx, or .xls files are supported")

    content = file.file.read()
    try:
        df = parse_uploaded_file(file.filename, content)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Could not parse file: {e}")

    if df.empty:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File has no data rows")

    headers = list(df.columns)
    mapping = auto_detect_mapping(headers)

    import_obj = Import(
        uploaded_by_user_id=current_user.id,
        original_filename=file.filename,
        status=ImportStatus.MAPPED if mapping else ImportStatus.UPLOADED,
        column_mapping=mapping,
        total_rows=len(df),
    )
    db.add(import_obj)
    db.flush()

    for i, row in enumerate(df.to_dict(orient="records"), start=1):
        db.add(ImportRow(import_id=import_obj.id, row_number=i, raw_data=row))

    db.commit()
    db.refresh(import_obj)
    return import_obj


@router.post("/{import_id}/map-columns", response_model=ImportOut)
def map_columns(
    import_id: str, payload: MapColumnsRequest,
    current_user: User = Depends(_import_roles), db: Session = Depends(get_db),
):
    import_obj = db.query(Import).filter(Import.id == import_id).first()
    if not import_obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import not found")

    import_obj.column_mapping = payload.column_mapping
    import_obj.status = ImportStatus.MAPPED
    db.commit()
    db.refresh(import_obj)
    return import_obj


@router.get("/{import_id}/preview", response_model=PreviewResponse)
def preview_import(
    import_id: str, sample_size: int = 20,
    current_user: User = Depends(_import_roles), db: Session = Depends(get_db),
):
    import_obj = db.query(Import).filter(Import.id == import_id).first()
    if not import_obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import not found")
    if not import_obj.column_mapping:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Map columns before previewing (POST /map-columns)")

    validate_import(db, import_obj)  # re-runs every time -- cheap for hackathon-scale files, always fresh

    sample = (
        db.query(ImportRow).filter(ImportRow.import_id == import_id)
        .order_by(ImportRow.row_number).limit(sample_size).all()
    )
    errors = (
        db.query(ImportValidationError).filter(ImportValidationError.import_id == import_id)
        .order_by(ImportValidationError.row_number).limit(200).all()
    )

    return PreviewResponse(
        import_id=import_obj.id, status=import_obj.status.value,
        total_rows=import_obj.total_rows, valid_rows=import_obj.valid_rows, error_rows=import_obj.error_rows,
        sample_rows=[PreviewRowOut(row_number=r.row_number, is_valid=r.is_valid, raw_data=r.raw_data) for r in sample],
        error_summary=[ValidationErrorOut.model_validate(e) for e in errors],
    )


@router.get("/{import_id}/errors", response_model=list[ValidationErrorOut])
def get_import_errors(
    import_id: str, current_user: User = Depends(_import_roles), db: Session = Depends(get_db),
):
    errors = (
        db.query(ImportValidationError).filter(ImportValidationError.import_id == import_id)
        .order_by(ImportValidationError.row_number).all()
    )
    return errors


@router.post("/{import_id}/confirm", response_model=ConfirmResponse)
def confirm_import_route(
    import_id: str, current_user: User = Depends(_import_roles), db: Session = Depends(get_db),
):
    import_obj = db.query(Import).filter(Import.id == import_id).first()
    if not import_obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import not found")
    if import_obj.status != ImportStatus.PREVIEWED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Run /preview before confirming")

    created = confirm_import(db, import_obj)
    return ConfirmResponse(import_id=import_obj.id, status=import_obj.status.value, projects_created=created)
