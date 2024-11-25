from fastapi import Depends
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.validator import validate_token
from src.schema.login import AuthResponse
# from src.storage.db import get_db
from .router import router


@router.post("/info", response_model=AuthResponse)
def info(
    token: str = Depends(validate_token),
    # session: AsyncSession = Depends(get_db),
) -> ORJSONResponse:

    return ORJSONResponse(token)
