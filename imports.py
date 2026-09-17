from pydantic import BaseModel


class ImportOut(BaseModel):
    id: str
    original_filename: str
    status: str
    column_mapping: dict | None
    total_rows: int
    valid_rows: int
    error_rows: int

    model_config = {"from_attributes": True}


class MapColumnsRequest(BaseModel):
    column_mapping: dict[str, str]  # {"CSV Header": "canonical_field_name"}


class ValidationErrorOut(BaseModel):
    row_number: int
    rule_code: str
    severity: str
    message: str
    field_name: str | None

    model_config = {"from_attributes": True}


class PreviewRowOut(BaseModel):
    row_number: int
    is_valid: bool
    raw_data: dict


class PreviewResponse(BaseModel):
    import_id: str
    status: str
    total_rows: int
    valid_rows: int
    error_rows: int
    sample_rows: list[PreviewRowOut]
    error_summary: list[ValidationErrorOut]


class ConfirmResponse(BaseModel):
    import_id: str
    status: str
    projects_created: int
