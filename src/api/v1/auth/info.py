from fastapi import Depends
from fastapi.responses import ORJSONResponse

from src.auth.validator import validate_token
from src.schema.login import AuthResponse
from .router import router


@router.post("/info", response_model=AuthResponse)
def info(
    token: str = Depends(validate_token),
) -> ORJSONResponse:

    return ORJSONResponse(token)
