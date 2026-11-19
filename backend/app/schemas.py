from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Trimmed before validation, so whitespace-only input is rejected rather than stored.
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]

# Auth


class PasscodeIn(BaseModel):
    passcode: str = Field(min_length=1, max_length=200)


class AuthStatus(BaseModel):
    authenticated: bool


# Memories


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    created_at: datetime
    updated_at: datetime


class DeletedCount(BaseModel):
    deleted: int


# Realtime


class RealtimeSessionOut(BaseModel):
    client_secret: str
    expires_at: int
    model: str


# Tools (called by the browser on the model's behalf)


class RememberIn(BaseModel):
    content: ShortText
    replaces_id: int | None = None


class RememberOut(BaseModel):
    status: Literal["saved", "updated"]
    memory: MemoryOut


class ForgetIn(BaseModel):
    memory_id: int


class ForgetOut(BaseModel):
    status: Literal["forgotten", "not_found"]


class WebSearchIn(BaseModel):
    query: ShortText


class Source(BaseModel):
    title: str
    url: str


class WebSearchOut(BaseModel):
    answer: str
    sources: list[Source]
