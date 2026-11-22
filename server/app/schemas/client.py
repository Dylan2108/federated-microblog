"""Formato de entrada y salida de la API que usa la interfaz."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
from app.domain.entities import MAX_NOTE_LENGTH

class RegisterIn(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9_]{1,30}$")
    password: str = Field(min_length=6)
    display_name: str = Field(default="", max_length=50)

class LoginIn(BaseModel):
    username: str
    password: str

class TokenOut(BaseModel):
    token: str

class UserOut(BaseModel):
    id: str
    username: str
    domain: str
    handle: str
    display_name: str
    is_local: bool
    locked: bool
    model_config = {"from_attributes": True}

class ProfileIn(BaseModel):
    """Campos omitidos = no se cambian."""
    display_name: str | None = Field(default=None, min_length=1, max_length=50)
    locked: bool | None = None

class FollowOut(BaseModel):
    state: Literal["accepted", "pending"]

Visibility = Literal["public", "unlisted", "followers"]

class NoteEditIn(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_NOTE_LENGTH)

class NoteIn(NoteEditIn):
    visibility: Visibility = "public"

class NoteOut(BaseModel):
    id: str
    author: UserOut
    content: str
    visibility: Visibility
    published: datetime
    updated: datetime | None = None
    reposted_by: UserOut | None = None

    model_config = {"from_attributes": True}