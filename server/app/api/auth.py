from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user, get_repos
from app.core.security import create_token
from app.domain.entities import Actor
from app.domain.ports import Repos
from app.schemas.client import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import users

router = APIRouter(prefix="/api", tags=["auth"])

@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: RegisterIn, repos: Repos = Depends(get_repos)):
    try:
        return await users.register(repos, body.username, body.password, body.display_name)
    except users.UsernameTaken:
        raise HTTPException(409,"Ese nombre de usuario ya existe")

@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, repos: Repos = Depends(get_repos)):
    actor = await users.authenticate(repos, body.username, body.password)
    if actor is None:
        raise HTTPException(401,"Usuario o contrasena incorrectos")
    return TokenOut(token=create_token(actor.username))

@router.get("/me", response_model=UserOut)
async def me(user: Actor = Depends(get_current_user)):
    return user