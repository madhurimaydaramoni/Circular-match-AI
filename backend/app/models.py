from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sector: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    listings: Mapped[list["MaterialListing"]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    organization_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped[Optional[Organization]] = relationship(back_populates="users")
    material_listings: Mapped[list["MaterialListing"]] = relationship(back_populates="owner")
    requirements: Mapped[list["BuyerRequirement"]] = relationship(back_populates="user")
    reviews: Mapped[list["VerificationReview"]] = relationship(back_populates="reviewer")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="actor")


class MaterialListing(Base):
    __tablename__ = "material_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    material_type: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(60), default="available")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    public_summary: Mapped[str] = mapped_column(Text, nullable=False)
    sensitive_notes: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(60), default="tonnes")
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    price_per_ton: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    price_unit: Mapped[str] = mapped_column(String(20), default="INR/tonne", nullable=False)
    price_original_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_original_currency_code: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    price_original_unit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    gst_rate_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gst_inclusive: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    price_source_org: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    price_source_title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    price_source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    price_publication_date: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    price_retrieved_date: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    price_geographic_coverage: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    price_grade: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    price_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    price_verification_status: Mapped[str] = mapped_column(String(40), default="unverified", nullable=False)
    price_valid_until: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    price_status: Mapped[str] = mapped_column(String(40), default="unavailable", nullable=False)
    price_limitations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_last_updated: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(40), default="unverified", nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    demo_label: Mapped[str] = mapped_column(String(120), default="DEMONSTRATION DATA")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped[Organization] = relationship(back_populates="listings")
    owner: Mapped[User] = relationship(back_populates="material_listings")
    properties: Mapped[list["MaterialProperty"]] = relationship(back_populates="listing")
    reviews: Mapped[list["VerificationReview"]] = relationship(back_populates="listing")
    access_requests: Mapped[list["AccessRequest"]] = relationship(back_populates="listing")
    matches: Mapped[list["MatchResult"]] = relationship(back_populates="listing")


class EmissionFactor(Base):
    __tablename__ = "emission_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    factor_type: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(100), nullable=False)
    source_org: Mapped[str] = mapped_column(String(200), nullable=False)
    source_title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    publication_date: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    retrieved_date: Mapped[str] = mapped_column(String(40), nullable=False)
    geographic_coverage: Mapped[str] = mapped_column(String(200), nullable=False)
    reporting_year: Mapped[int] = mapped_column(Integer, nullable=False)
    assumptions: Mapped[str] = mapped_column(Text, default="")
    methodology: Mapped[str] = mapped_column(Text, default="")
    verification_status: Mapped[str] = mapped_column(String(40), default="unverified", nullable=False)
    limitations: Mapped[str] = mapped_column(Text, default="")


class SourcedReference(Base):
    __tablename__ = "sourced_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    reference_type: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    qualifier: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    unit: Mapped[str] = mapped_column(String(100), nullable=False)
    currency_code: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    reporting_period: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_org: Mapped[str] = mapped_column(String(240), nullable=False)
    source_title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    publication_date: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    retrieved_date: Mapped[str] = mapped_column(String(40), nullable=False)
    geographic_coverage: Mapped[str] = mapped_column(String(200), nullable=False)
    material_grade: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    data_classification: Mapped[str] = mapped_column(String(60), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False)
    methodology: Mapped[str] = mapped_column(Text, default="")
    limitations: Mapped[str] = mapped_column(Text, default="")
    last_updated: Mapped[str] = mapped_column(String(40), nullable=False)


class MaterialProperty(Base):
    __tablename__ = "material_properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_listings.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[str] = mapped_column(String(160), nullable=False)
    unit: Mapped[str] = mapped_column(String(60), default="")
    source: Mapped[str] = mapped_column(String(120), default="Company-declared")
    status: Mapped[str] = mapped_column(String(50), default="Verified")
    date: Mapped[str] = mapped_column(String(40), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    listing: Mapped[MaterialListing] = relationship(back_populates="properties")


class BuyerRequirement(Base):
    __tablename__ = "buyer_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    material_category: Mapped[str] = mapped_column(String(120), nullable=False)
    technical_specs: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(60), default="tonnes")
    max_distance_km: Mapped[float] = mapped_column(Float, default=250.0)
    location: Mapped[str] = mapped_column(String(200), default="")
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    safety_constraints: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="requirements")
    matches: Mapped[list["MatchResult"]] = relationship(back_populates="requirement")


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    requirement_id: Mapped[int] = mapped_column(Integer, ForeignKey("buyer_requirements.id"), nullable=False)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_listings.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reasons: Mapped[str] = mapped_column(Text, default="")
    breakdown: Mapped[str] = mapped_column(Text, default="")
    warnings: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    requirement: Mapped[BuyerRequirement] = relationship(back_populates="matches")
    listing: Mapped[MaterialListing] = relationship(back_populates="matches")


class VerificationReview(Base):
    __tablename__ = "verification_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_listings.id"), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    property_name: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    notes: Mapped[str] = mapped_column(Text, default="")
    evidence_url: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    listing: Mapped[MaterialListing] = relationship(back_populates="reviews")
    reviewer: Mapped[User] = relationship(back_populates="reviews")


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_listings.id"), nullable=False)
    seeker_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    listing: Mapped[MaterialListing] = relationship(back_populates="access_requests")


class SupplierQuotationRequest(Base):
    __tablename__ = "supplier_quotation_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_listings.id"), nullable=False)
    requester_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    requested_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    delivery_location: Mapped[str] = mapped_column(String(240), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    listing: Mapped[MaterialListing] = relationship()
    requester: Mapped[User] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    actor: Mapped[User] = relationship(back_populates="audit_events")


class ImpactCalculation(Base):
    __tablename__ = "impact_calculations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    material_type: Mapped[str] = mapped_column(String(160), nullable=False)
    inputs: Mapped[dict] = mapped_column(JSON, default={})
    result: Mapped[dict] = mapped_column(JSON, default={})
    assumptions: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
