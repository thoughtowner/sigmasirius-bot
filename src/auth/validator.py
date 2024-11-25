from typing import Annotated

import jwt
from fastapi import Header, HTTPException
from starlette import status


def validate_token(
    authorization: Annotated[str, Header()],
) -> dict[str, any]:
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

    return parsed_token
