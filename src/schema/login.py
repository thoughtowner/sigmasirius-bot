from pydantic import BaseModel


class AuthPost(BaseModel):
    login: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    exp: int
