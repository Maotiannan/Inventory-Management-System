import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: uuid.UUID
    username: str
    role: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfo


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class UserReadResponse(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ItemCreate(BaseModel):
    table_id: uuid.UUID
    name: str
    code: str
    quantity: int = 0
    image_original: str | None = None
    image_thumb: str | None = None
    notes: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class ItemUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    quantity: int | None = None
    image_original: str | None = None
    image_thumb: str | None = None
    notes: str | None = None
    properties: dict[str, Any] | None = None
    properties_patch: dict[str, Any] | None = None
    properties_remove: list[str] | None = None


class ItemRead(BaseModel):
    id: uuid.UUID
    table_id: uuid.UUID
    name: str
    code: str
    quantity: int
    image_original: str | None
    image_thumb: str | None
    notes: str | None
    properties: dict[str, Any]
    updated_at: datetime

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    original_path: str
    thumb_path: str
    original_url: str
    thumb_url: str


class StockInRequest(BaseModel):
    table_id: uuid.UUID
    code: str
    quantity: int = Field(gt=0)
    name: str | None = None
    notes: str | None = None
    properties: dict[str, Any] | None = None


class StockOutRequest(BaseModel):
    table_id: uuid.UUID
    code: str
    quantity: int = Field(gt=0)
    notes: str | None = None


class ApiKeyCreateRequest(BaseModel):
    name: str = "默认密钥"


class ApiKeyCreatedResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    api_key: str
    created_at: datetime


class ApiKeyReadResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    api_key: str
    active: bool
    created_at: datetime
    last_used_at: datetime | None


class LogReadResponse(BaseModel):
    id: uuid.UUID
    operator_id: uuid.UUID | None
    operator_username: str | None = None
    auth_source: str | None = None
    auth_label: str | None = None
    action: str
    target: str
    summary: str
    detail: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
