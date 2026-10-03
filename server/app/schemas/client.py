"""Formato de entrada y salida de la API que usa la interfaz."""

from datetime import datetime
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
    display_name: str
    model_config = {"from_attributes": True}

class NoteIn(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_NOTE_LENGTH)

class NoteOut(BaseModel):
    id: str
    author: UserOut
    content: str
    published: datetime

    model_config = {"from_attributes": True}