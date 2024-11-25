import jwt
from fastapi.responses import ORJSONResponse

from src.schema.login import AuthResponse, AuthPost
from .router import router


@router.post("/login", response_model=AuthResponse)
def home(
    body: AuthPost
) -> ORJSONResponse:

    encoded = jwt.encode(
        {
            "login": body.login,
            "password": body.password,
        },
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    )

    return ORJSONResponse({"access_token": encoded, "exp": 123123})
