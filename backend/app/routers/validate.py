import logging
from fastapi import APIRouter
from app.models import ValidateRequest, ValidateResponse
from app.services.validator import validate_llms_txt

logger = logging.getLogger("app.router.validate")

router = APIRouter()


@router.post("/validate", response_model=ValidateResponse)
async def validate(req: ValidateRequest):
    logger.info("Validating markdown (%d chars)", len(req.markdown))
    issues = validate_llms_txt(req.markdown)
    logger.info("Validation result: valid=%s, %d issues", len(issues) == 0, len(issues))
    return ValidateResponse(valid=len(issues) == 0, issues=issues)
