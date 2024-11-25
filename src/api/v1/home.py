from fastapi.responses import JSONResponse, ORJSONResponse

from .router import router


@router.get("/home")
def home() -> JSONResponse:
    return ORJSONResponse({"message": "Hello"})
