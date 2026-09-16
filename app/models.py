from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class EquipmentStatus(str, Enum):
    AVAILABLE = "available"
    MAINTENANCE = "maintenance"
    RESERVED = "reserved"


# --- AUTH SCHEMAS ---

class LoginRequest(BaseModel):
    tenant_id: int
    email: str
    password: str


# --- TENANT SCHEMAS ---

class TenantCreate(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Apex Tool Rentals"})


class TenantResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- USER SCHEMAS ---

class UserCreate(BaseModel):
    tenant_id: int = Field(..., description="ID of the tenant business")
    email: EmailStr
    password: str = Field(..., min_length=6, description="User account password")
    role: UserRole = UserRole.USER


class UserResponse(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    role: UserRole
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- EQUIPMENT SCHEMAS ---

class EquipmentCreate(BaseModel):
    tenant_id: Optional[int] = Field(None, description="Inferred automatically from auth JWT if omitted")
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    daily_rate: float = Field(..., gt=0, description="Daily rate must be greater than zero")
    status: EquipmentStatus = EquipmentStatus.AVAILABLE


class EquipmentUpdate(BaseModel):
    name: str
    description: Optional[str] = None
    daily_rate: float
    status: EquipmentStatus


class EquipmentBatchArchive(BaseModel):
    equipment_ids: List[int]


class EquipmentResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    description: Optional[str] = None
    daily_rate: float
    status: EquipmentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- RESERVATION SCHEMAS ---

class ReservationCreate(BaseModel):
    tenant_id: Optional[int] = Field(None, description="Inferred automatically from auth JWT if omitted")
    user_id: int
    equipment_id: int
    start_date: datetime
    end_date: datetime


class ReservationUpdate(BaseModel):
    start_date: datetime
    end_date: datetime
    total_cost: float
    payment_status: str


class ReservationResponse(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    equipment_id: int
    start_date: datetime
    end_date: datetime
    total_cost: float
    payment_intent_id: Optional[str] = None
    payment_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

