from typing import Annotated

import jwt
from fastapi import Header, HTTPException
from fastapi.responses import ORJSONResponse
from starlette import status

from src.schema.login import AuthResponse
from .router import router


@router.post("/info", response_model=AuthResponse)
def info(
    authorization: Annotated[str, Header()]
) -> ORJSONResponse:
    schema, token = authorization.split()
    if schema.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    try:
        parsed_token = jwt.decode(
            token,
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            algorithms=["HS256"],
        )
    except jwt.InvalidSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return ORJSONResponse(parsed_token)
