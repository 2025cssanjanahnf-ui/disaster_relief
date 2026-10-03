from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ----------------------------------------------------
# User Schemas
# ----------------------------------------------------
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)
    role: str = Field(default="REQUESTER")


class UserLogin(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


# ----------------------------------------------------
# Resource Schemas
# ----------------------------------------------------
class ResourceBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    category: str = Field(..., min_length=2, max_length=50)
    quantity_available: int = Field(..., ge=0)
    location: str = Field(..., min_length=2, max_length=100)


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    quantity_available: Optional[int] = Field(None, ge=0)
    location: Optional[str] = None


class ResourceOut(ResourceBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True


# ----------------------------------------------------
# Relief Request Schemas
# ----------------------------------------------------
class ReliefRequestBase(BaseModel):
    resource_id: int
    requested_quantity: int = Field(..., gt=0)
    location: str = Field(..., min_length=2, max_length=150)
    urgency: str = Field(default="Medium")  # "Low", "Medium", "High", "Critical"
    description: Optional[str] = None


class ReliefRequestCreate(ReliefRequestBase):
    pass


class ReliefRequestOut(ReliefRequestBase):
    id: int
    priority_score: float
    status: str
    requested_by: int
    created_at: datetime
    updated_at: datetime
    priority_level: Optional[str] = None
    waiting_time_display: Optional[str] = None

    class Config:
        from_attributes = True


# ----------------------------------------------------
# Delivery Schemas
# ----------------------------------------------------
class DeliveryCreate(BaseModel):
    request_id: int
    resource_id: int
    assigned_to: str = Field(..., min_length=2, max_length=100)
    vehicle_details: str = Field(..., min_length=2, max_length=100)


class DeliveryStatusUpdate(BaseModel):
    status: str  # "Assigned", "In Transit", "Delivered"


class DeliveryOut(BaseModel):
    id: int
    request_id: int
    resource_id: int
    assigned_to: str
    vehicle_details: str
    status: str
    assigned_at: datetime
    delivered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ----------------------------------------------------
# Dashboard & Shortage Schemas
# ----------------------------------------------------
class ShortageItem(BaseModel):
    resource_id: int
    resource_name: str
    category: str
    location: str
    available_quantity: int
    expected_demand: int
    shortage_quantity: int


class DashboardStats(BaseModel):
    pending_requests_count: int
    critical_requests_count: int
    escalated_requests_count: int
    available_resources_count: int
    current_shortages_count: int
    delivered_requests_count: int
