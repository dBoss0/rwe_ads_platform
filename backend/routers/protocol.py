"""Protocol upload and parsing endpoints."""
import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.config import settings
from backend.models.protocol import ParseRequest, ParseResponse
from backend.services import parser as parser_svc

router = APIRouter(tags=["protocol"])


@router.post("/parse", response_model=ParseResponse)
async def parse_protocol_text(request: ParseRequest):
    """
    Parse a protocol from a UC Volume path or pasted text.

    - volume_path: /Volumes/catalog/schema/vol/study.docx (Databricks only)
    - raw_text:    pasted protocol text (works in all modes)
    """
    try:
        result = parser_svc.parse_protocol(
            volume_path=request.volume_path,
            raw_text=request.raw_text,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parse failed: {e}")


@router.post("/upload", response_model=ParseResponse)
async def upload_and_parse_protocol(file: UploadFile = File(...)):
    """
    Upload a protocol file (DOCX or PDF) and parse it immediately.

    Databricks mode:
      - Uploads to UC Volume → calls ai_parse_document (full AI pipeline)

    Local / dev mode:
      - Saves to temp file → python-docx extraction → Claude REST parse
    """
    allowed = {".docx", ".pdf"}
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Upload DOCX or PDF.",
        )

    content = await file.read()

    # Write to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if settings.is_databricks_app and settings.protocol_volume:
            # Databricks: upload to UC Volume then parse via full AI pipeline
            from backend.services.databricks_client import upload_to_volume
            volume_path = f"{settings.protocol_volume}/{file.filename}"
            upload_to_volume(tmp_path, volume_path)
            result = parser_svc.parse_protocol(volume_path=volume_path)
        else:
            # Local dev: parse directly from temp DOCX with Claude REST
            result = parser_svc.parse_protocol(local_file_path=tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parse failed: {e}")
    finally:
        os.unlink(tmp_path)

    return result
