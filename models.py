from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="REQUESTER")  # "ADMIN", "REQUESTER"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    requests = relationship("ReliefRequest", back_populates="requester", cascade="all, delete-orphan")


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    quantity_available = Column(Integer, nullable=False, default=0)
    location = Column(String(100), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    requests = relationship("ReliefRequest", back_populates="resource")
    deliveries = relationship("Delivery", back_populates="resource")


class ReliefRequest(Base):
    __tablename__ = "relief_requests"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    requested_quantity = Column(Integer, nullable=False)
    location = Column(String(150), nullable=False)
    urgency = Column(String(20), nullable=False, default="Medium")  # "Low", "Medium", "High", "Critical"
    description = Column(Text, nullable=True)
    priority_score = Column(Float, nullable=False, default=0.0)
    status = Column(String(30), nullable=False, default="Pending")
    # Statuses: "Pending", "Approved", "Rejected", "Resource Allocated", "Delivery Assigned", "In Transit", "Delivered", "Escalated"
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    resource = relationship("Resource", back_populates="requests")
    requester = relationship("User", back_populates="requests")
    delivery = relationship("Delivery", back_populates="request", uselist=False, cascade="all, delete-orphan")

    @property
    def priority_level(self) -> str:
        """Return human-readable priority level based on priority_score."""
        if self.priority_score >= 80:
            return "CRITICAL"
        elif self.priority_score >= 50:
            return "HIGH"
        elif self.priority_score >= 25:
            return "MEDIUM"
        return "LOW"

    @property
    def waiting_time_minutes(self) -> int:
        """Calculate elapsed waiting time in minutes since creation."""
        now = datetime.now(timezone.utc)
        created = self.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        delta = now - created
        return max(0, int(delta.total_seconds() // 60))

    @property
    def waiting_time_display(self) -> str:
        mins = self.waiting_time_minutes
        if mins < 60:
            return f"{mins}m"
        hours = mins // 60
        remaining_mins = mins % 60
        return f"{hours}h {remaining_mins}m"


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("relief_requests.id"), nullable=False, unique=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    assigned_to = Column(String(100), nullable=False)
    vehicle_details = Column(String(100), nullable=False)
    status = Column(String(30), nullable=False, default="Assigned")  # "Assigned", "In Transit", "Delivered"
    assigned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    delivered_at = Column(DateTime, nullable=True)

    # Relationships
    request = relationship("ReliefRequest", back_populates="delivery")
    resource = relationship("Resource", back_populates="deliveries")
