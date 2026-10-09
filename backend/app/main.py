from __future__ import annotations

import hashlib
import math
import os
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .models import (
    AccessRequest,
    AuditEvent,
    Base,
    BuyerRequirement,
    EmissionFactor,
    ImpactCalculation,
    MaterialListing,
    MaterialProperty,
    MatchResult,
    Organization,
    SourcedReference,
    SupplierQuotationRequest,
    User,
    VerificationReview,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "circularmatch.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
engine_options: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
if DATABASE_URL in {"sqlite://", "sqlite:///:memory:"}:
    engine_options["poolclass"] = StaticPool
engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

CITY_STATE = {
    "hyderabad": ("Hyderabad", "Telangana"),
    "pune": ("Pune", "Maharashtra"),
    "coimbatore": ("Coimbatore", "Tamil Nadu"),
    "bengaluru": ("Bengaluru", "Karnataka"),
    "mysuru": ("Mysuru", "Karnataka"),
    "vizag": ("Visakhapatnam", "Andhra Pradesh"),
    "visakhapatnam": ("Visakhapatnam", "Andhra Pradesh"),
    "nagpur": ("Nagpur", "Maharashtra"),
    "chennai": ("Chennai", "Tamil Nadu"),
    "jaipur": ("Jaipur", "Rajasthan"),
    "ahmedabad": ("Ahmedabad", "Gujarat"),
}
INDIAN_STATES = {
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
}


def migrate_schema() -> None:
    """Apply additive SQLite migrations without replacing or deleting user data."""
    columns = {column["name"] for column in inspect(engine).get_columns("material_listings")}
    additions = {
        "currency_code": "VARCHAR(3) NOT NULL DEFAULT 'UNK'",
        "price_unit": "VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN'",
        "price_original_amount": "FLOAT",
        "price_original_currency_code": "VARCHAR(3)",
        "price_original_unit": "VARCHAR(40)",
        "gst_rate_percent": "FLOAT",
        "gst_inclusive": "BOOLEAN",
        "price_source_org": "VARCHAR(200)",
        "price_source_title": "VARCHAR(300)",
        "price_source_url": "VARCHAR(500)",
        "price_publication_date": "VARCHAR(40)",
        "price_retrieved_date": "VARCHAR(40)",
        "price_geographic_coverage": "VARCHAR(200)",
        "price_grade": "VARCHAR(160)",
        "price_type": "VARCHAR(40)",
        "price_verification_status": "VARCHAR(40) NOT NULL DEFAULT 'unverified'",
        "price_valid_until": "VARCHAR(40)",
        "price_status": "VARCHAR(40) NOT NULL DEFAULT 'unavailable'",
        "price_limitations": "TEXT",
        "price_last_updated": "VARCHAR(40)",
        "city": "VARCHAR(100)",
        "state": "VARCHAR(100)",
        "verification_status": "VARCHAR(40) NOT NULL DEFAULT 'unverified'",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.exec_driver_sql(f"ALTER TABLE material_listings ADD COLUMN {name} {definition}")
        for city, state in {
            "Hyderabad": "Telangana",
            "Pune": "Maharashtra",
            "Coimbatore": "Tamil Nadu",
            "Bengaluru": "Karnataka",
            "Mysuru": "Karnataka",
            "Vizag": "Andhra Pradesh",
            "Nagpur": "Maharashtra",
            "Chennai": "Tamil Nadu",
            "Jaipur": "Rajasthan",
        }.items():
            normalized_city = "Visakhapatnam" if city == "Vizag" else city
            connection.exec_driver_sql(
                "UPDATE material_listings SET city = ?, state = ? "
                "WHERE city IS NULL AND lower(location) = lower(?)",
                (normalized_city, state, city),
            )
        requirement_columns = {column["name"] for column in inspect(engine).get_columns("buyer_requirements")}
        for name in ("city", "state"):
            if name not in requirement_columns:
                connection.exec_driver_sql(f"ALTER TABLE buyer_requirements ADD COLUMN {name} VARCHAR(100)")
        for city, state in {
            "Hyderabad": "Telangana",
            "Pune": "Maharashtra",
            "Coimbatore": "Tamil Nadu",
            "Bengaluru": "Karnataka",
            "Mysuru": "Karnataka",
            "Vizag": "Andhra Pradesh",
            "Nagpur": "Maharashtra",
            "Chennai": "Tamil Nadu",
            "Jaipur": "Rajasthan",
        }.items():
            normalized_city = "Visakhapatnam" if city == "Vizag" else city
            connection.exec_driver_sql(
                "UPDATE buyer_requirements SET city = ?, state = ? "
                "WHERE city IS NULL AND lower(location) = lower(?)",
                (normalized_city, state, city),
            )


migrate_schema()

security = HTTPBearer()
SECRET_KEY = os.getenv("SECRET_KEY", "this-is-a-very-strong-secret-key-32-bytes-long")
ALGORITHM = "HS256"

app = FastAPI(title="CircularMatch AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash.startswith("pbkdf2_sha256$"):
        return False
    _, salt, digest_hex = password_hash.split("$", 2)
    expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()
    return secrets.compare_digest(expected, digest_hex)


def create_access_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=12),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "organization_id": user.organization_id,
        "organization": user.organization.name if user.organization else None,
    }


def serialize_sourced_reference(reference: SourcedReference) -> dict[str, Any]:
    return {
        "id": reference.id,
        "slug": reference.slug,
        "reference_type": reference.reference_type,
        "name": reference.name,
        "value": reference.value,
        "qualifier": reference.qualifier,
        "unit": reference.unit,
        "currency_code": reference.currency_code,
        "reporting_period": reference.reporting_period,
        "source_org": reference.source_org,
        "source_title": reference.source_title,
        "source_url": reference.source_url,
        "publication_date": reference.publication_date,
        "retrieved_date": reference.retrieved_date,
        "geographic_coverage": reference.geographic_coverage,
        "material_grade": reference.material_grade,
        "data_classification": reference.data_classification,
        "verification_status": reference.verification_status,
        "methodology": reference.methodology,
        "limitations": reference.limitations,
        "last_updated": reference.last_updated,
    }


def log_event(db: Session, actor_id: int, action: str, entity_type: str, entity_id: int, details: str):
    db.add(
        AuditEvent(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )
    db.commit()


def user_has_access(current_user: User | None, listing: MaterialListing, db: Session) -> bool:
    if current_user is None:
        return False
    if current_user.id == listing.owner_id or current_user.role in {"admin", "verifier"}:
        return True
    request = (
        db.query(AccessRequest)
        .filter(
            AccessRequest.listing_id == listing.id,
            AccessRequest.seeker_id == current_user.id,
            AccessRequest.status == "approved",
        )
        .first()
    )
    return request is not None or listing.is_public


def listing_has_price(listing: MaterialListing) -> bool:
    if listing.price_valid_until is None or listing.price_status != "valid":
        return False
    try:
        if date.fromisoformat(listing.price_valid_until) < date.today():
            return False
    except ValueError:
        return False
    return (
        listing.price_per_ton is not None
        and listing.currency_code == "INR"
        and listing.price_unit == "INR/tonne"
        and listing.price_type in {"official", "official_quote", "market_quote", "supplier_quote"}
        and bool(listing.price_source_org and listing.price_source_title)
        and (
            listing.price_source_url is None
            or listing.price_source_url.startswith(("https://", "http://"))
        )
        and bool(listing.price_geographic_coverage and listing.price_grade)
        and bool(listing.price_retrieved_date)
    )


def price_available_filter():
    return and_(
        MaterialListing.price_per_ton.is_not(None),
        MaterialListing.currency_code == "INR",
        MaterialListing.price_unit == "INR/tonne",
        MaterialListing.price_type.in_(("official", "official_quote", "market_quote", "supplier_quote")),
        MaterialListing.price_status == "valid",
        MaterialListing.price_valid_until >= date.today().isoformat(),
        MaterialListing.price_source_org.is_not(None),
        MaterialListing.price_source_title.is_not(None),
        MaterialListing.price_geographic_coverage.is_not(None),
        MaterialListing.price_grade.is_not(None),
        MaterialListing.price_retrieved_date.is_not(None),
    )


def serialize_property(prop: MaterialProperty, demonstration: bool) -> dict[str, Any]:
    return {
        "id": prop.id,
        "name": prop.name,
        "value": prop.value,
        "unit": prop.unit,
        "source": "Demonstration data" if demonstration else prop.source,
        "status": "Unverified" if demonstration else prop.status,
        "date": prop.date,
        "notes": f"DEMONSTRATION DATA: {prop.notes}" if demonstration else prop.notes,
    }


def serialize_listing(listing: MaterialListing, current_user: User | None, db: Session) -> dict[str, Any]:
    visible = current_user is not None and user_has_access(current_user, listing, db)
    price_available = listing_has_price(listing)
    demonstration = listing.demo_label == "DEMONSTRATION DATA"
    data: dict[str, Any] = {
        "id": listing.id,
        "title": listing.title,
        "material_type": listing.material_type,
        "category": listing.category,
        "organization_id": listing.organization_id,
        "organization": listing.organization.name if listing.organization else None,
        "status": listing.status,
        "description": listing.description,
        "public_summary": listing.public_summary,
        "quantity": listing.quantity,
        "unit": listing.unit,
        "location": listing.location,
        "price_per_ton": listing.price_per_ton if price_available else None,
        "price_amount": listing.price_per_ton if price_available else None,
        "legacy_price_amount": listing.price_per_ton if listing.currency_code == "UNK" else None,
        "currency_code": listing.currency_code,
        "price_unit": listing.price_unit,
        "price_original_amount": listing.price_original_amount,
        "price_original_currency_code": listing.price_original_currency_code,
        "price_original_unit": listing.price_original_unit,
        "price_available": price_available,
        "gst_rate_percent": listing.gst_rate_percent,
        "gst_inclusive": listing.gst_inclusive,
        "price_source_org": listing.price_source_org,
        "price_source_title": listing.price_source_title,
        "price_source_url": listing.price_source_url,
        "price_publication_date": listing.price_publication_date,
        "price_retrieved_date": listing.price_retrieved_date,
        "price_geographic_coverage": listing.price_geographic_coverage,
        "price_grade": listing.price_grade,
        "price_type": listing.price_type,
        "price_verification_status": listing.price_verification_status,
        "price_valid_until": listing.price_valid_until,
        "price_status": (
            "unavailable" if listing.price_per_ton is None or listing.currency_code != "INR"
            else "expired" if listing.price_valid_until and listing.price_valid_until < date.today().isoformat()
            else "demonstration" if listing.demo_label == "DEMONSTRATION DATA"
            else listing.price_status
        ),
        "price_limitations": listing.price_limitations,
        "price_last_updated": listing.price_last_updated,
        "city": listing.city,
        "state": listing.state,
        "verification_status": listing.verification_status,
        "is_public": listing.is_public,
        "demo_label": listing.demo_label,
        "created_at": listing.created_at.isoformat(),
        "updated_at": listing.updated_at.isoformat(),
        "owner_id": listing.owner_id,
    }
    if visible:
        data["sensitive_notes"] = listing.sensitive_notes
        data["properties"] = [serialize_property(prop, demonstration) for prop in listing.properties]
    else:
        data["sensitive_notes"] = "Access restricted. Submit a request for confidential fields and documents."
        data["properties"] = [
            {
                **serialize_property(prop, demonstration),
                "value": prop.value if prop.status in {"Verified", "Company-declared"} and not demonstration else "Not disclosed",
                "notes": prop.notes if prop.status in {"Verified", "Company-declared"} and not demonstration else "Restricted",
            }
            for prop in listing.properties
        ]
    return data


def serialize_requirement(requirement: BuyerRequirement) -> dict[str, Any]:
    return {
        "id": requirement.id,
        "user_id": requirement.user_id,
        "title": requirement.title,
        "material_category": requirement.material_category,
        "technical_specs": requirement.technical_specs,
        "quantity": requirement.quantity,
        "unit": requirement.unit,
        "max_distance_km": requirement.max_distance_km,
        "location": requirement.location,
        "city": requirement.city,
        "state": requirement.state,
        "safety_constraints": requirement.safety_constraints,
        "created_at": requirement.created_at.isoformat(),
    }


def quantity_in_tonnes(quantity: float, unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized in {"kg", "kilogram", "kilograms"}:
        return quantity / 1000
    if normalized in {"tonne", "tonnes", "t", "metric ton", "metric tons"}:
        return quantity
    raise HTTPException(status_code=400, detail="Quantity unit must be kg or tonnes")


def normalize_price(payload: dict) -> tuple[float | None, float | None, str | None]:
    original_amount = payload.get("price_original_amount")
    if original_amount is None:
        standard_amount = payload.get("price_per_tonne", payload.get("price_per_ton"))
        if standard_amount is None:
            return None, None, None
        amount = float(standard_amount)
        original_unit = payload.get("price_original_unit") or "INR/tonne"
        original_currency = payload.get("price_original_currency_code") or "INR"
        if original_currency != "INR":
            raise HTTPException(status_code=400, detail="Only INR source prices can be normalized; other currencies require an explicitly sourced conversion.")
        if original_unit not in {"INR/tonne", "INR/t"}:
            raise HTTPException(status_code=400, detail="Enter the published amount/unit separately for INR/kg price normalization.")
        return amount, amount, original_unit
    original_amount = float(original_amount)
    original_currency = payload.get("price_original_currency_code") or "INR"
    original_unit = payload.get("price_original_unit")
    if original_currency != "INR":
        raise HTTPException(status_code=400, detail="Only INR source prices can be normalized; other currencies require an explicitly sourced conversion.")
    if original_unit == "INR/kg":
        normalized_amount = original_amount * 1000
    elif original_unit in {"INR/tonne", "INR/t"}:
        normalized_amount = original_amount
    else:
        raise HTTPException(status_code=400, detail="Original price unit must be INR/kg or INR/tonne.")
    supplied_standard = payload.get("price_per_tonne", payload.get("price_per_ton"))
    if supplied_standard is not None and not math.isclose(float(supplied_standard), normalized_amount, rel_tol=1e-9):
        raise HTTPException(status_code=400, detail="Normalized price conflicts with original price amount and unit.")
    if not math.isfinite(normalized_amount) or normalized_amount < 0:
        raise HTTPException(status_code=400, detail="Price must be finite and non-negative.")
    return normalized_amount, original_amount, original_unit


def serialize_factor(factor: EmissionFactor) -> dict[str, Any]:
    return {
        "id": factor.id,
        "factor_type": factor.factor_type,
        "name": factor.name,
        "value": factor.value,
        "unit": factor.unit,
        "source_org": factor.source_org,
        "source_title": factor.source_title,
        "source_url": factor.source_url,
        "publication_date": factor.publication_date,
        "retrieved_date": factor.retrieved_date,
        "geographic_coverage": factor.geographic_coverage,
        "reporting_year": factor.reporting_year,
        "assumptions": factor.assumptions,
        "methodology": factor.methodology,
        "verification_status": factor.verification_status,
        "limitations": factor.limitations,
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload["sub"])
    except Exception as exc:  # pragma: no cover - auth failure path
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*allowed_roles):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Allowed roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker


def get_user_listings_for_role(user: User, db: Session):
    if user.role == "producer":
        return db.query(MaterialListing).filter((MaterialListing.organization_id == user.organization_id) | (MaterialListing.owner_id == user.id))
    if user.role == "admin":
        return db.query(MaterialListing)
    if user.role == "verifier":
        return db.query(MaterialListing)
    approved_ids = [
        item.listing_id for item in db.query(AccessRequest).filter(AccessRequest.seeker_id == user.id, AccessRequest.status == "approved").all()
    ]
    return db.query(MaterialListing).filter((MaterialListing.is_public.is_(True)) | (MaterialListing.id.in_(approved_ids)))


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            seed_demo_data(db)
        seed_sourced_references(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "app": "CircularMatch AI"}


@app.get("/api")
def api_root():
    return {"message": "CircularMatch AI API is running."}


@app.post("/api/auth/login")
def login(payload: dict | None = None, username: str | None = None, password: str | None = None, db: Session = Depends(get_db)):
    if payload:
        username = payload.get("username")
        password = payload.get("password")
    if not username or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username and password are required")
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {
        "token": create_access_token(user),
        "user": serialize_user(user),
    }


@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"user": serialize_user(current_user)}


@app.get("/api/dashboard")
def get_dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    material_count = db.query(MaterialListing).count()
    public_count = db.query(MaterialListing).filter(MaterialListing.is_public.is_(True)).count()
    requirement_count = db.query(BuyerRequirement).count()
    pending_requests = db.query(AccessRequest).filter(AccessRequest.status == "pending").count()
    verified_listings = db.query(MaterialListing).filter(MaterialListing.verification_status == "verified").count()
    impact_rows = db.query(ImpactCalculation.result).all()
    estimated_inr_benefit = sum(
        float(row[0].get("net_economic_benefit_inr") or 0)
        for row in impact_rows
        if row[0] and row[0].get("currency_code") == "INR"
    )
    return {
        "user": serialize_user(current_user),
        "stats": {
            "materials": material_count,
            "public_materials": public_count,
            "requirements": requirement_count,
            "pending_requests": pending_requests,
            "verified_listings": verified_listings,
            "estimated_economic_benefit_inr": round(estimated_inr_benefit, 2),
        },
    }


@app.get("/api/data-sources")
def get_data_sources(db: Session = Depends(get_db)):
    references = db.query(SourcedReference).order_by(SourcedReference.reference_type, SourcedReference.name).all()
    return {"items": [serialize_sourced_reference(item) for item in references]}


@app.get("/api/materials")
def list_materials(
    search: str | None = Query(default=None),
    state: str | None = Query(default=None),
    city: str | None = Query(default=None),
    category: str | None = Query(default=None),
    price_available: bool | None = Query(default=None),
    verification_status: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    queryset = get_user_listings_for_role(current_user, db)
    if search:
        s = f"%{search.lower()}%"
        queryset = queryset.filter(
            (MaterialListing.title.ilike(s))
            | (MaterialListing.material_type.ilike(s))
            | (MaterialListing.category.ilike(s))
            | (MaterialListing.location.ilike(s))
        )
    if state:
        queryset = queryset.filter(MaterialListing.state.ilike(state))
    if city:
        queryset = queryset.filter(MaterialListing.city.ilike(city))
    if category:
        queryset = queryset.filter(MaterialListing.category.ilike(category))
    if price_available is True:
        queryset = queryset.filter(price_available_filter())
    elif price_available is False:
        queryset = queryset.filter(~price_available_filter())
    if verification_status:
        queryset = queryset.filter(MaterialListing.verification_status == verification_status)
    listings = queryset.order_by(MaterialListing.created_at.desc()).all()
    return {"items": [serialize_listing(item, current_user, db) for item in listings]}


@app.get("/api/marketplace")
def marketplace(
    state: str | None = Query(default=None),
    city: str | None = Query(default=None),
    category: str | None = Query(default=None),
    price_available: bool | None = Query(default=None),
    verification_status: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(MaterialListing).filter(MaterialListing.is_public.is_(True))
    if state:
        query = query.filter(MaterialListing.state.ilike(state))
    if city:
        query = query.filter(MaterialListing.city.ilike(city))
    if category:
        query = query.filter(MaterialListing.category.ilike(category))
    if price_available is True:
        query = query.filter(price_available_filter())
    elif price_available is False:
        query = query.filter(~price_available_filter())
    if verification_status:
        query = query.filter(MaterialListing.verification_status == verification_status)
    items = query.order_by(MaterialListing.created_at.desc()).all()
    return {"items": [serialize_listing(item, current_user, db) for item in items]}


@app.get("/api/materials/{listing_id}")
def get_material_detail(listing_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    listing = db.get(MaterialListing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Material not found")
    return {"item": serialize_listing(listing, current_user, db)}


@app.post("/api/materials", status_code=201)
def create_material(
    payload: dict,
    current_user: User = Depends(require_roles("producer", "admin")),
    db: Session = Depends(get_db),
):
    org = db.get(Organization, current_user.organization_id) if current_user.organization_id else None
    if not org and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="Producer must belong to an organization")
    unit = payload.get("unit") or "tonnes"
    quantity = float(payload.get("quantity") or 0)
    quantity_in_tonnes(quantity, unit)
    city = payload.get("city")
    state = payload.get("state")
    if city and not state:
        resolved = CITY_STATE.get(city.strip().lower())
        state = resolved[1] if resolved else None
    if state and state not in INDIAN_STATES:
        raise HTTPException(status_code=400, detail="Select a valid Indian state")
    location = ", ".join(value for value in (city, state) if value) or payload.get("location") or "Not specified"
    price, original_price_amount, original_price_unit = normalize_price(payload)
    currency_code = payload.get("currency_code") or "INR"
    if currency_code != "INR" or (
        price is not None and (not math.isfinite(float(price)) or float(price) < 0)
    ):
        raise HTTPException(status_code=400, detail="New listing prices must be non-negative INR per tonne")
    price_type = payload.get("price_type") if price is not None else None
    if price_type not in {None, "official", "official_quote", "market_quote", "supplier_quote", "estimate"}:
        raise HTTPException(status_code=400, detail="A wholesale price index cannot be listed as an absolute material price")
    if price is not None and not payload.get("price_retrieved_date"):
        raise HTTPException(status_code=400, detail="Enter the date you retrieved or received this quotation.")
    price_valid_until = payload.get("price_valid_until")
    if price is not None:
        try:
            if not price_valid_until or date.fromisoformat(str(price_valid_until)) < date.today():
                raise ValueError
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Enter a valid price expiry date that is today or later.")
    if price is not None and any(
        not payload.get(field)
        for field in ("price_source_org", "price_source_title", "price_source_url", "price_geographic_coverage", "price_grade")
    ):
        raise HTTPException(status_code=400, detail="Priced records require source, geographic coverage, and grade metadata.")
    if price_type in {"official", "official_quote"} and any(
        not payload.get(field)
        for field in ("price_source_org", "price_source_title", "price_source_url", "price_publication_date", "price_geographic_coverage", "price_grade")
    ):
        raise HTTPException(status_code=400, detail="Official prices require source, publication date, coverage, and material-grade metadata")
    if payload.get("price_source_url") and not str(payload["price_source_url"]).startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="Price source URL must be HTTP(S)")
    gst_rate = payload.get("gst_rate_percent")
    if gst_rate is not None and not 0 <= float(gst_rate) <= 100:
        raise HTTPException(status_code=400, detail="GST rate must be between 0 and 100 percent")
    listing = MaterialListing(
        title=payload.get("title") or "New material listing",
        material_type=payload.get("material_type") or "Industrial by-product",
        category=payload.get("category") or "General",
        organization_id=current_user.organization_id or org.id if org else 1,
        owner_id=current_user.id,
        status=payload.get("status") or "available",
        description=payload.get("description") or payload.get("public_summary") or "User-submitted listing; details not provided.",
        public_summary=payload.get("public_summary") or "No public summary supplied by the user.",
        sensitive_notes=payload.get("sensitive_notes") or "",
        quantity=quantity,
        unit=unit,
        location=location,
        city=city,
        state=state,
        price_per_ton=float(price) if price is not None else None,
        currency_code=currency_code,
        price_unit="INR/tonne",
        price_original_amount=original_price_amount,
        price_original_currency_code=(payload.get("price_original_currency_code") or "INR") if price is not None else None,
        price_original_unit=original_price_unit,
        gst_rate_percent=float(gst_rate) if gst_rate is not None else None,
        gst_inclusive=payload.get("gst_inclusive"),
        price_source_org=payload.get("price_source_org"),
        price_source_title=payload.get("price_source_title"),
        price_source_url=payload.get("price_source_url"),
        price_publication_date=payload.get("price_publication_date"),
        price_retrieved_date=payload.get("price_retrieved_date"),
        price_geographic_coverage=payload.get("price_geographic_coverage"),
        price_grade=payload.get("price_grade"),
        price_type=price_type,
        price_verification_status="unverified",
        price_valid_until=price_valid_until,
        price_status="valid" if price is not None else "unavailable",
        price_limitations=payload.get("price_limitations"),
        price_last_updated=date.today().isoformat() if price is not None else None,
        is_public=bool(payload.get("is_public", True)),
        demo_label="USER-SUBMITTED DATA",
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    log_event(db, current_user.id, "create_listing", "material", listing.id, "Producer created a listing")
    return {"item": serialize_listing(listing, current_user, db)}


@app.put("/api/materials/{listing_id}")
def update_material(listing_id: int, payload: dict, current_user: User = Depends(require_roles("producer", "admin")), db: Session = Depends(get_db)):
    listing = db.get(MaterialListing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Material not found")
    if listing.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You can only update your own listings")
    for field in [
        "title", "material_type", "category", "status", "description", "public_summary", "sensitive_notes",
        "quantity", "unit", "location", "city", "state", "price_per_ton", "currency_code", "price_original_amount",
        "price_original_currency_code", "price_original_unit", "gst_rate_percent",
        "gst_inclusive", "price_source_org", "price_source_title", "price_source_url", "price_publication_date",
        "price_retrieved_date", "price_geographic_coverage", "price_grade", "price_type",
        "price_limitations", "is_public",
    ]:
        if field in payload:
            setattr(listing, field, payload[field])
    price_value_submitted = any(key in payload for key in ("price_per_tonne", "price_per_ton", "price_original_amount"))
    if "currency_code" in payload and not price_value_submitted and payload["currency_code"] != listing.currency_code:
        raise HTTPException(status_code=400, detail="Currency cannot be changed without entering a new price amount")
    if "currency_code" in payload and payload["currency_code"] != "INR":
        raise HTTPException(status_code=400, detail="New listing prices must be in INR")
    if price_value_submitted:
        normalized_price, original_price_amount, original_price_unit = normalize_price(payload)
        if "currency_code" in payload and payload["currency_code"] != "INR":
            raise HTTPException(status_code=400, detail="New listing prices must be in INR")
        listing.price_per_ton = normalized_price
        listing.currency_code = "INR"
        listing.price_unit = "INR/tonne"
        listing.price_original_amount = original_price_amount
        listing.price_original_currency_code = (payload.get("price_original_currency_code") or "INR") if normalized_price is not None else None
        listing.price_original_unit = original_price_unit
    price_was_modified = price_value_submitted
    if price_was_modified and listing.price_per_ton is not None:
        if listing.demo_label == "DEMONSTRATION DATA":
            raise HTTPException(status_code=400, detail="Demonstration listings cannot be given supplier prices.")
        if listing.currency_code != "INR" or float(listing.price_per_ton) < 0:
            raise HTTPException(status_code=400, detail="Listing prices must be non-negative INR per tonne")
        if not listing.price_retrieved_date:
            raise HTTPException(status_code=400, detail="Enter the date you retrieved or received this quotation.")
        try:
            valid_until = date.fromisoformat(str(payload.get("price_valid_until") or ""))
        except ValueError:
            raise HTTPException(status_code=400, detail="Enter a valid price expiry date.")
        if valid_until < date.today():
            raise HTTPException(status_code=400, detail="Price expiry date must be today or later.")
        listing.price_valid_until = valid_until.isoformat()
        listing.price_status = "valid"
        listing.price_type = payload.get("price_type") or listing.price_type or "supplier_quote"
        if any(
            not getattr(listing, field)
            for field in ("price_source_org", "price_source_title", "price_geographic_coverage", "price_grade")
        ):
            raise HTTPException(status_code=400, detail="Supplier prices require source, geographic coverage, and grade/quality.")
        if listing.price_type == "index":
            raise HTTPException(status_code=400, detail="A wholesale price index cannot be listed as an absolute material price")
        if listing.price_type in {"official", "official_quote"} and any(
            not getattr(listing, field)
            for field in ("price_source_org", "price_source_title", "price_source_url", "price_publication_date", "price_geographic_coverage", "price_grade")
        ):
            raise HTTPException(status_code=400, detail="Official prices require complete source and comparability metadata")
        if listing.gst_rate_percent is not None and not 0 <= float(listing.gst_rate_percent) <= 100:
            raise HTTPException(status_code=400, detail="GST rate must be between 0 and 100 percent")
        listing.price_unit = "INR/tonne"
        listing.price_last_updated = date.today().isoformat()
    if listing.unit:
        quantity_in_tonnes(float(listing.quantity), listing.unit)
    if listing.state and listing.state not in INDIAN_STATES:
        raise HTTPException(status_code=400, detail="Select a valid Indian state")
    db.commit()
    log_event(db, current_user.id, "update_listing", "material", listing.id, "Updated listing details")
    return {"item": serialize_listing(listing, current_user, db)}


@app.put("/api/materials/{listing_id}/price")
def update_material_price(
    listing_id: int,
    payload: dict,
    current_user: User = Depends(require_roles("producer", "admin")),
    db: Session = Depends(get_db),
):
    listing = db.get(MaterialListing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Material not found")
    if current_user.role != "admin" and listing.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update prices for your own listings")
    if listing.demo_label == "DEMONSTRATION DATA":
        raise HTTPException(
            status_code=400,
            detail="Demonstration listings cannot be given supplier prices; create a real supplier listing instead.",
        )
    if payload.get("currency_code") != "INR":
        raise HTTPException(status_code=400, detail="Supplier prices must be entered in INR; unknown currencies cannot be converted.")
    try:
        price = float(payload["price_per_tonne"])
        valid_until = date.fromisoformat(str(payload["price_valid_until"]))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Enter a numeric price and valid price expiry date.")
    if not math.isfinite(price) or price < 0:
        raise HTTPException(status_code=400, detail="Price must be finite and non-negative.")
    if valid_until < date.today():
        raise HTTPException(status_code=400, detail="Price expiry date must be today or later.")
    source_org = str(payload.get("price_source_org") or "").strip()
    if not source_org:
        raise HTTPException(status_code=400, detail="Supplier/source name is required.")
    source_url = payload.get("price_source_url")
    if source_url and not str(source_url).startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="Price source URL must be HTTP(S).")
    gst_rate = payload.get("gst_rate_percent")
    if gst_rate is not None:
        try:
            gst_rate = float(gst_rate)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="GST rate must be a number between 0 and 100.")
        if not math.isfinite(gst_rate) or not 0 <= gst_rate <= 100:
            raise HTTPException(status_code=400, detail="GST rate must be between 0 and 100 percent.")

    listing.price_per_ton = price
    listing.currency_code = "INR"
    listing.price_unit = "INR/tonne"
    listing.price_original_amount = price
    listing.price_original_currency_code = "INR"
    listing.price_original_unit = "INR/tonne"
    listing.price_source_org = source_org
    listing.price_source_title = str(payload.get("price_source_title") or "Supplier quotation").strip()
    listing.price_source_url = source_url
    listing.price_retrieved_date = date.today().isoformat()
    listing.price_geographic_coverage = str(payload.get("price_geographic_coverage") or listing.location)
    listing.price_grade = str(payload.get("price_grade") or listing.material_type)
    listing.price_type = "supplier_quote"
    listing.price_valid_until = valid_until.isoformat()
    listing.price_status = "valid"
    listing.price_verification_status = "unverified"
    listing.price_limitations = payload.get("price_limitations")
    listing.gst_rate_percent = gst_rate
    listing.gst_inclusive = payload.get("gst_inclusive")
    listing.price_last_updated = date.today().isoformat()
    db.commit()
    db.refresh(listing)
    log_event(db, current_user.id, "update_material_price", "material", listing.id, "Updated supplier quotation")
    return {"item": serialize_listing(listing, current_user, db)}


@app.get("/api/requirements")
def get_requirements(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in {"seeker", "admin"}:
        return {"items": []}
    items = db.query(BuyerRequirement).filter(BuyerRequirement.user_id == current_user.id).order_by(BuyerRequirement.created_at.desc()).all()
    return {"items": [serialize_requirement(item) for item in items]}


@app.post("/api/requirements", status_code=201)
def create_requirement(payload: dict, current_user: User = Depends(require_roles("seeker", "admin")), db: Session = Depends(get_db)):
    quantity = float(payload.get("quantity") or 0)
    unit = payload.get("unit") or "tonnes"
    quantity_in_tonnes(quantity, unit)
    city = payload.get("city")
    state = payload.get("state")
    if city and not state:
        resolved = CITY_STATE.get(city.strip().lower())
        state = resolved[1] if resolved else None
    if state and state not in INDIAN_STATES:
        raise HTTPException(status_code=400, detail="Select a valid Indian state")
    requirement = BuyerRequirement(
        user_id=current_user.id,
        title=payload.get("title") or "Required material",
        material_category=payload.get("material_category") or "construction",
        technical_specs=payload.get("technical_specs") or "",
        quantity=quantity,
        unit=unit,
        max_distance_km=float(payload.get("max_distance_km") or 250),
        location=", ".join(value for value in (city, state) if value) or payload.get("location") or "",
        city=city,
        state=state,
        safety_constraints=payload.get("safety_constraints") or "",
    )
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    log_event(db, current_user.id, "submit_requirement", "requirement", requirement.id, "Seeker submitted a requirement")
    return {"item": serialize_requirement(requirement)}


@app.get("/api/matches")
def list_matches(requirement_id: int | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if requirement_id is None:
        rows = db.query(MatchResult).all()
        return {"items": [
            {
                "id": row.id,
                "requirement_id": row.requirement_id,
                "listing_id": row.listing_id,
                "score": row.score,
                "reasons": row.reasons,
                "breakdown": row.breakdown,
                "warnings": row.warnings,
                "listing": serialize_listing(row.listing, current_user, db),
            }
            for row in rows
        ]}
    requirement = db.get(BuyerRequirement, requirement_id)
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")
    items = db.query(MatchResult).filter(MatchResult.requirement_id == requirement_id).all()
    return {"items": [
        {
            "id": item.id,
            "requirement_id": item.requirement_id,
            "listing_id": item.listing_id,
            "score": item.score,
            "reasons": item.reasons,
            "breakdown": item.breakdown,
            "warnings": item.warnings,
            "listing": serialize_listing(item.listing, current_user, db),
        }
        for item in items
    ]}


@app.post("/api/matches")
def generate_matches(payload: dict, current_user: User = Depends(require_roles("seeker", "admin")), db: Session = Depends(get_db)):
    requirement_id = payload.get("requirement_id")
    if not requirement_id:
        raise HTTPException(status_code=400, detail="Requirement ID is required")
    requirement = db.get(BuyerRequirement, requirement_id)
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")
    if requirement.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You cannot match another user's requirement")

    db.query(MatchResult).filter(MatchResult.requirement_id == requirement_id).delete()
    listings = db.query(MaterialListing).filter(MaterialListing.is_public.is_(True)).all()
    results = []
    for listing in listings:
        score = 0
        reasons = []
        breakdown = []
        warnings = []
        if requirement.material_category.lower() in listing.material_type.lower():
            score += 30
            reasons.append("Material category aligns with requested by-product type.")
        elif requirement.material_category.lower() in listing.category.lower():
            score += 22
            reasons.append("Related category match found.")
        else:
            warnings.append("Category mismatch requires analyst review.")
        if quantity_in_tonnes(listing.quantity, listing.unit) >= quantity_in_tonnes(requirement.quantity, requirement.unit):
            score += 20
            breakdown.append("Quantity compatibility: available stock suffices")
        else:
            warnings.append("Quantity is lower than requested volume.")
        if listing.status == "available":
            score += 15
            breakdown.append("Current availability supports matching")
        if listing.location and requirement.location:
            if requirement.location.lower() in listing.location.lower():
                score += 15
                breakdown.append("Location is compatible with requested region")
            else:
                warnings.append("Transport distance may be material for final compliance review")
        if listing_has_price(listing):
            score += 10
            breakdown.append("Price data is available for decision support")
        if score >= 60:
            reasons.append("Qualified match for demonstration scoring.")
        else:
            warnings.append("Further technical review is required before field use.")
        score = min(100, max(15, score))
        if not warnings:
            warnings.append("No critical safety warnings recorded for this demo match.")
        row = MatchResult(
            requirement_id=requirement.id,
            listing_id=listing.id,
            score=score,
            reasons="; ".join(reasons),
            breakdown="; ".join(breakdown),
            warnings="; ".join(warnings),
        )
        db.add(row)
        results.append(row)
    db.commit()
    return {"items": [
        {
            "id": item.id,
            "requirement_id": item.requirement_id,
            "listing_id": item.listing_id,
            "score": item.score,
            "reasons": item.reasons,
            "breakdown": item.breakdown,
            "warnings": item.warnings,
            "listing": serialize_listing(item.listing, current_user, db),
        }
        for item in results
    ]}


@app.get("/api/verification")
def get_verification(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in {"verifier", "admin"}:
        return {"items": []}
    rows = db.query(VerificationReview).order_by(VerificationReview.created_at.desc()).all()
    return {"items": [
        {
            "id": review.id,
            "listing_id": review.listing_id,
            "property_name": review.property_name,
            "status": review.status,
            "notes": review.notes,
            "evidence_url": review.evidence_url,
            "reviewer": serialize_user(review.reviewer),
            "listing_title": review.listing.title,
        }
        for review in rows
    ]}


@app.post("/api/verification/{listing_id}/review")
def review_listing(listing_id: int, payload: dict, current_user: User = Depends(require_roles("verifier", "admin")), db: Session = Depends(get_db)):
    listing = db.get(MaterialListing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    review = VerificationReview(
        listing_id=listing.id,
        reviewer_id=current_user.id,
        property_name=payload.get("property_name") or "general review",
        status=payload.get("status") or "approved",
        notes=payload.get("notes") or "Review approved by demo verifier.",
        evidence_url=payload.get("evidence_url") or "",
    )
    if review.status == "rejected":
        listing.verification_status = "rejected"
    elif review.status == "pending":
        listing.verification_status = "pending"
    elif review.status == "approved" and review.evidence_url.startswith(("https://", "http://")):
        listing.verification_status = "verified"
    else:
        listing.verification_status = "unverified"
    if "price" in review.property_name.lower() or "quote" in review.property_name.lower():
        if review.status == "approved" and review.evidence_url.startswith(("https://", "http://")):
            listing.price_verification_status = "verified"
        elif review.status == "rejected":
            listing.price_verification_status = "rejected"
        elif review.status == "pending":
            listing.price_verification_status = "pending"
        else:
            listing.price_verification_status = "unverified"
    db.add(review)
    db.commit()
    db.refresh(review)
    log_event(db, current_user.id, "verify_listing", "listing", listing.id, f"Reviewed {listing.title}")
    return {"item": {"id": review.id, "status": review.status, "notes": review.notes}}


@app.get("/api/access-requests")
def get_access_requests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "seeker":
        rows = db.query(AccessRequest).filter(AccessRequest.seeker_id == current_user.id).all()
    elif current_user.role == "producer":
        rows = db.query(AccessRequest).join(MaterialListing).filter(MaterialListing.organization_id == current_user.organization_id).all()
    else:
        rows = db.query(AccessRequest).all()
    return {"items": [
        {
            "id": item.id,
            "listing_id": item.listing_id,
            "listing_title": item.listing.title,
            "seeker_id": item.seeker_id,
            "reason": item.reason,
            "status": item.status,
            "created_at": item.created_at.isoformat(),
        }
        for item in rows
    ]}


@app.post("/api/access-requests", status_code=201)
def request_access(payload: dict, current_user: User = Depends(require_roles("seeker", "admin")), db: Session = Depends(get_db)):
    listing_id = payload.get("listing_id")
    if not listing_id:
        raise HTTPException(status_code=400, detail="listing_id is required")
    listing = db.get(MaterialListing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Owners do not need access requests for their own listings")
    request = AccessRequest(
        listing_id=listing.id,
        seeker_id=current_user.id,
        reason=payload.get("reason") or "Need confidential material details for a reuse evaluation.",
        status="pending",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    log_event(db, current_user.id, "request_access", "access_request", request.id, f"Requested access to {listing.title}")
    return {"item": {"id": request.id, "status": request.status}}


@app.get("/api/quotation-requests")
def get_quotation_requests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(SupplierQuotationRequest)
    if current_user.role == "seeker":
        query = query.filter(SupplierQuotationRequest.requester_id == current_user.id)
    elif current_user.role == "producer":
        query = query.join(MaterialListing).filter(
            MaterialListing.organization_id == current_user.organization_id
        )
    elif current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Role cannot view supplier quotation requests.")
    rows = query.order_by(SupplierQuotationRequest.created_at.desc()).all()
    return {
        "items": [
            {
                "id": row.id,
                "listing_id": row.listing_id,
                "listing_title": row.listing.title,
                "requester_id": row.requester_id,
                "requested_quantity": row.requested_quantity,
                "quantity_unit": row.quantity_unit,
                "delivery_location": row.delivery_location,
                "message": row.message,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@app.post("/api/quotation-requests", status_code=201)
def create_quotation_request(
    payload: dict,
    current_user: User = Depends(require_roles("seeker", "admin")),
    db: Session = Depends(get_db),
):
    listing_id = payload.get("listing_id")
    listing = db.get(MaterialListing, listing_id) if listing_id else None
    if listing is None:
        raise HTTPException(status_code=404, detail="Material listing not found.")
    if listing.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot request a quotation for your own listing.")
    if not user_has_access(current_user, listing, db):
        raise HTTPException(status_code=403, detail="You do not have access to request a quotation for this listing.")
    if listing_has_price(listing):
        raise HTTPException(status_code=400, detail="This material already has a valid listed price.")
    try:
        quantity = float(payload.get("requested_quantity"))
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError
        unit = str(payload.get("quantity_unit") or "tonnes")
        quantity_in_tonnes(quantity, unit)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Requested quantity must be positive and use kg or tonnes.")
    location = str(payload.get("delivery_location") or "").strip()
    if not location:
        raise HTTPException(status_code=400, detail="Delivery location is required.")
    message = str(payload.get("message") or "").strip()
    if len(message) > 2000:
        raise HTTPException(status_code=400, detail="Message must be 2,000 characters or fewer.")

    request = SupplierQuotationRequest(
        listing_id=listing.id,
        requester_id=current_user.id,
        requested_quantity=quantity,
        quantity_unit=unit,
        delivery_location=location,
        message=message,
        status="pending",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    log_event(
        db,
        current_user.id,
        "request_supplier_quotation",
        "quotation_request",
        request.id,
        f"Requested supplier quotation for {listing.title}",
    )
    return {
        "item": {
            "id": request.id,
            "listing_id": request.listing_id,
            "listing_title": listing.title,
            "requested_quantity": request.requested_quantity,
            "quantity_unit": request.quantity_unit,
            "delivery_location": request.delivery_location,
            "message": request.message,
            "status": request.status,
            "created_at": request.created_at.isoformat(),
        }
    }


@app.post("/api/access-requests/{request_id}/decision")
def decide_access_request(request_id: int, payload: dict, current_user: User = Depends(require_roles("producer", "admin")), db: Session = Depends(get_db)):
    request = db.get(AccessRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    listing = db.get(MaterialListing, request.listing_id)
    if listing and listing.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only the material owner can decide this request")
    decision = payload.get("decision")
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be approved or rejected")
    request.status = decision
    request.updated_at = datetime.utcnow()
    db.commit()
    log_event(db, current_user.id, "decide_access", "access_request", request.id, f"Access request {decision}")
    return {"item": {"id": request.id, "status": request.status}}


@app.get("/api/analytics")
def analytics(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    public_listings = db.query(MaterialListing).filter(MaterialListing.is_public.is_(True)).all()
    quantity_sum = sum(quantity_in_tonnes(row.quantity, row.unit) for row in public_listings)
    active_requirements = db.query(BuyerRequirement).count()
    scores = [row[0] for row in db.query(MatchResult.score).all()]
    grouped: dict[str, float] = {}
    for listing in public_listings:
        grouped[listing.material_type] = grouped.get(listing.material_type, 0) + quantity_in_tonnes(listing.quantity, listing.unit)
    return {
        "metrics": {
            "public_materials": len(public_listings),
            "quantity_tonnes": round(quantity_sum, 2),
            "requirements": active_requirements,
            "avg_match_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
        },
        "labels": list(grouped),
        "series": [round(quantity, 2) for quantity in grouped.values()],
        "quantity_unit": "tonnes",
    }


@app.get("/api/emission-factors")
def get_emission_factors(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    factors = db.query(EmissionFactor).order_by(EmissionFactor.factor_type, EmissionFactor.reporting_year.desc()).all()
    return {"items": [serialize_factor(factor) for factor in factors]}


@app.post("/api/emission-factors", status_code=201)
def create_emission_factor(
    payload: dict,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    allowed_types = {"transport", "processing", "avoided_disposal", "virgin_substitution", "grid_electricity"}
    if payload.get("factor_type") not in allowed_types:
        raise HTTPException(status_code=400, detail="Unsupported emission factor type")
    required = ("name", "value", "unit", "source_org", "source_title", "source_url", "geographic_coverage", "reporting_year")
    if any(not payload.get(field) for field in required):
        raise HTTPException(status_code=400, detail="Factor value and complete source metadata are required")
    if not payload.get("retrieved_date"):
        raise HTTPException(status_code=400, detail="Enter the date the source was actually retrieved.")
    if not math.isfinite(float(payload["value"])) or float(payload["value"]) < 0 or not str(payload["source_url"]).startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="Factor value must be non-negative and source URL must be HTTP(S)")
    expected_units = {
        "transport": "kgCO2e/tonne-km",
        "processing": "kgCO2e/tonne",
        "avoided_disposal": "kgCO2e/tonne",
        "virgin_substitution": "kgCO2e/tonne",
        "grid_electricity": "kgCO2e/kWh",
    }
    if payload["unit"] != expected_units[payload["factor_type"]]:
        raise HTTPException(status_code=400, detail=f"Factor unit must be {expected_units[payload['factor_type']]}")
    verification_status = payload.get("verification_status", "unverified")
    if verification_status not in {"unverified", "verified", "pending"}:
        raise HTTPException(status_code=400, detail="Invalid factor verification status")
    factor = EmissionFactor(
        factor_type=payload["factor_type"],
        name=payload["name"],
        value=float(payload["value"]),
        unit=payload["unit"],
        source_org=payload["source_org"],
        source_title=payload["source_title"],
        source_url=payload["source_url"],
        publication_date=payload.get("publication_date"),
        retrieved_date=payload["retrieved_date"],
        geographic_coverage=payload["geographic_coverage"],
        reporting_year=int(payload["reporting_year"]),
        assumptions=payload.get("assumptions") or "",
        methodology=payload.get("methodology") or "",
        verification_status=verification_status,
        limitations=payload.get("limitations") or "",
    )
    db.add(factor)
    db.commit()
    db.refresh(factor)
    return {"item": serialize_factor(factor)}


@app.post("/api/calculator")
def calculate_impact(payload: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mass = payload.get("mass_tonnes", payload.get("mass_tons", payload.get("mass")))
    unit = payload.get("mass_unit", "tonnes")
    distance = payload.get("distance_km")
    if (
        mass is None
        or distance is None
        or not math.isfinite(float(mass))
        or not math.isfinite(float(distance))
        or float(mass) <= 0
        or float(distance) < 0
    ):
        return {"status": "insufficient_data", "message": "Provide a positive mass and a non-negative distance.", "result": None}
    mass_tonnes = quantity_in_tonnes(float(mass), unit)
    distance_km = float(distance)
    factor_ids = payload.get("factor_ids") or {}
    factors: dict[str, EmissionFactor] = {}
    for factor_type, factor_id in factor_ids.items():
        factor = db.get(EmissionFactor, int(factor_id))
        if not factor or factor.factor_type != factor_type or factor.verification_status != "verified":
            raise HTTPException(status_code=400, detail=f"No verified factor found for {factor_type}")
        factors[factor_type] = factor

    if "processing" in factors and "grid_electricity" in factors:
        raise HTTPException(status_code=400, detail="Use either a processing factor or grid electricity, not both, to avoid double counting.")
    if "grid_electricity" in factors:
        electricity_kwh = payload.get("electricity_kwh")
        if electricity_kwh is None or not math.isfinite(float(electricity_kwh)) or float(electricity_kwh) < 0:
            raise HTTPException(status_code=400, detail="A non-negative processing electricity value in kWh is required for the grid factor.")

    transport = None
    if "transport" in factors:
        transport = mass_tonnes * distance_km * factors["transport"].value
    processing = None
    if "processing" in factors:
        processing = mass_tonnes * factors["processing"].value
    elif "grid_electricity" in factors:
        processing = float(payload["electricity_kwh"]) * factors["grid_electricity"].value
    avoided_disposal = mass_tonnes * factors["avoided_disposal"].value if "avoided_disposal" in factors else None
    virgin_substitution = mass_tonnes * factors["virgin_substitution"].value if "virgin_substitution" in factors else None
    required_emissions = (transport, processing, avoided_disposal, virgin_substitution)
    net_emissions = (
        avoided_disposal + virgin_substitution - transport - processing
        if all(value is not None for value in required_emissions)
        else None
    )

    cost_rates = {
        "transport_cost_inr": ("transport_cost_inr_per_tonne_km", mass_tonnes * distance_km),
        "processing_cost_inr": ("processing_cost_inr_per_tonne", mass_tonnes),
        "avoided_disposal_savings_inr": ("avoided_disposal_savings_inr_per_tonne", mass_tonnes),
        "material_purchase_cost_inr": ("material_purchase_cost_inr_per_tonne", mass_tonnes),
    }
    costs: dict[str, float | None] = {}
    for key, (rate, multiplier) in cost_rates.items():
        rate_value = payload.get(rate)
        if rate_value is None:
            costs[key] = None
            continue
        rate_value = float(rate_value)
        if not math.isfinite(rate_value) or rate_value < 0:
            raise HTTPException(status_code=400, detail="INR cost inputs must be finite and non-negative")
        costs[key] = round(rate_value * multiplier, 2)
    cost_values = tuple(costs.values())
    net_economic = (
        costs["avoided_disposal_savings_inr"]
        - costs["transport_cost_inr"]
        - costs["processing_cost_inr"]
        - costs["material_purchase_cost_inr"]
        if all(value is not None for value in cost_values)
        else None
    )
    used_factors = {key: serialize_factor(value) for key, value in factors.items()}
    assumptions = "Factor records and user-provided INR cost inputs are reported separately. No independently verified savings are claimed."
    result = {
        "mass_tonnes": round(mass_tonnes, 4),
        "distance_km": distance_km,
        "transport_emissions_kgco2e": round(transport, 2) if transport is not None else None,
        "processing_emissions_kgco2e": round(processing, 2) if processing is not None else None,
        "avoided_disposal_kgco2e": round(avoided_disposal, 2) if avoided_disposal is not None else None,
        "virgin_substitution_kgco2e": round(virgin_substitution, 2) if virgin_substitution is not None else None,
        "net_emissions_benefit_kgco2e": round(net_emissions, 2) if net_emissions is not None else None,
        **costs,
        "net_economic_benefit_inr": round(net_economic, 2) if net_economic is not None else None,
        "currency_code": "INR",
        "factors": used_factors,
        "reporting_years": sorted({factor.reporting_year for factor in factors.values()}),
        "assumptions": assumptions,
    }
    sufficient = net_emissions is not None
    calculation = ImpactCalculation(
        user_id=current_user.id,
        material_type=payload.get("material_type") or "By-product",
        inputs=payload,
        result=result,
        assumptions=assumptions,
    )
    db.add(calculation)
    db.commit()
    return {
        "status": "ok" if sufficient else "insufficient_data",
        "message": "Environmental calculation has complete factor inputs." if sufficient else "Insufficient data: one or more sourced emissions factors are unavailable.",
        "result": result,
    }


@app.post("/api/materials/{listing_id}/documents")
async def upload_document(
    listing_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles("producer", "admin")),
    db: Session = Depends(get_db),
):
    listing = db.get(MaterialListing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only the owner can upload documents")
    allowed = {".pdf", ".doc", ".docx", ".csv", ".png", ".jpg", ".jpeg"}
    filename = file.filename or "document"
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported document type")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
    safe_name = f"{listing_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename.replace(' ', '_')}"
    save_path = UPLOAD_DIR / safe_name
    save_path.write_bytes(content)
    return {"status": "uploaded", "path": str(save_path), "filename": filename, "size": len(content)}


@app.get("/api/admin/review")
def admin_review(current_user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    requests = db.query(AccessRequest).all()
    events = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(20).all()
    return {
        "requests": [
            {
                "id": item.id,
                "listing_id": item.listing_id,
                "status": item.status,
                "reason": item.reason,
                "listing": item.listing.title,
            }
            for item in requests
        ],
        "audit_events": [
            {
                "id": item.id,
                "action": item.action,
                "entity_type": item.entity_type,
                "details": item.details,
                "created_at": item.created_at.isoformat(),
            }
            for item in events
        ],
    }


def seed_demo_data(db: Session):
    organizations = [
        Organization(name="GreenLoop Materials", sector="Construction", location="Hyderabad, Telangana", contact_email="hello@greenloop.example"),
        Organization(name="Rivervale Recyclers", sector="Metals", location="Pune, Maharashtra", contact_email="ops@rivervale.example"),
        Organization(name="BioCycle Industries", sector="Agri & Biomass", location="Coimbatore, Tamil Nadu", contact_email="info@biocycle.example"),
        Organization(name="ZeroWaste Solutions", sector="Packaging", location="Bengaluru, Karnataka", contact_email="team@zerowaste.example"),
    ]
    db.add_all(organizations)
    db.commit()

    user_records = [
        User(username="producer1", email="producer1@example.com", password_hash=hash_password("demo123"), role="producer", organization_id=organizations[0].id),
        User(username="seeker1", email="seeker1@example.com", password_hash=hash_password("demo123"), role="seeker", organization_id=organizations[1].id),
        User(username="verifier1", email="verifier1@example.com", password_hash=hash_password("demo123"), role="verifier", organization_id=organizations[2].id),
        User(username="admin", email="admin@example.com", password_hash=hash_password("demo123"), role="admin", organization_id=organizations[3].id),
    ]
    db.add_all(user_records)
    db.commit()

    materials = [
        {"title": "Fly Ash Cement Blend", "material_type": "Fly ash", "category": "construction", "organization_id": organizations[0].id, "owner_id": user_records[0].id, "status": "available", "description": "High-calcium fly ash suitable for blended cement and concrete admixtures.", "public_summary": "DEMONSTRATION DATA: Suitable as supplementary cementitious material for concrete and masonry production.", "sensitive_notes": "Confidential quality data and customer mix design details remain restricted.", "quantity": 4200.0, "unit": "tonnes", "location": "Hyderabad", "is_public": True},
        {"title": "Rice Husk Ash Pozzolan", "material_type": "Rice husk ash", "category": "construction", "organization_id": organizations[2].id, "owner_id": user_records[2].id, "status": "available", "description": "Amorphous silica-rich rice husk ash for pozzolanic applications.", "public_summary": "DEMONSTRATION DATA: Pozzolanic ash with strong silica content for cement replacement.", "sensitive_notes": "Private lab reports and product traceability are restricted by default.", "quantity": 1800.0, "unit": "tonnes", "location": "Coimbatore", "is_public": True},
        {"title": "Aluminium Scrap Extrusions", "material_type": "Aluminium scrap", "category": "metals", "organization_id": organizations[1].id, "owner_id": user_records[1].id, "status": "available", "description": "Clean extrusion offcuts retained in controlled inventory for remelting.", "public_summary": "DEMONSTRATION DATA: Clean aluminium extrusion scrap with predictable alloy mix.", "sensitive_notes": "Exact alloy breakdown and private logistics data restricted.", "quantity": 720.0, "unit": "tonnes", "location": "Pune", "is_public": True},
        {"title": "Steel Scrap Bundles", "material_type": "Steel scrap", "category": "metals", "organization_id": organizations[1].id, "owner_id": user_records[1].id, "status": "available", "description": "Cut and bundled steel scrap suitable for electric arc furnace feed.", "public_summary": "DEMONSTRATION DATA: Scrap steel with low contamination and manageable density.", "sensitive_notes": "Sensitive composition and contamination records remain restricted.", "quantity": 3500.0, "unit": "tonnes", "location": "Pune", "is_public": True},
        {"title": "Clean Sawdust Biomass", "material_type": "Sawdust", "category": "biomass", "organization_id": organizations[2].id, "owner_id": user_records[2].id, "status": "available", "description": "Dry sawdust produced by woodworking operations for boiler or pellet feed.", "public_summary": "DEMONSTRATION DATA: Low-moisture biomass fuel suitable for industrial boilers.", "sensitive_notes": "Moisture variance and supplier details are confidential.", "quantity": 1600.0, "unit": "tonnes", "location": "Coimbatore", "is_public": True},
        {"title": "Textile Waste for Fiber Recovery", "material_type": "Textile waste", "category": "textiles", "organization_id": organizations[3].id, "owner_id": user_records[3].id, "status": "available", "description": "Post-industrial textile waste stream sorted for recycling and fiber recovery.", "public_summary": "DEMONSTRATION DATA: Fiber-rich textile waste that may suit recycling and secondary fiber use.", "sensitive_notes": "Fiber composition and contamination records remain private.", "quantity": 900.0, "unit": "tonnes", "location": "Bengaluru", "is_public": True},
        {"title": "Glass Cullet", "material_type": "Glass waste", "category": "packaging", "organization_id": organizations[3].id, "owner_id": user_records[3].id, "status": "available", "description": "Sorted glass cullet generated from packaging and flat glass processing.", "public_summary": "DEMONSTRATION DATA: Reusable glass cullet for secondary glass production.", "sensitive_notes": "Private sorting reports and contamination levels are withheld.", "quantity": 2800.0, "unit": "tonnes", "location": "Bengaluru", "is_public": True},
        {"title": "Plastic Process Scrap", "material_type": "Plastic production scrap", "category": "plastics", "organization_id": organizations[3].id, "owner_id": user_records[3].id, "status": "available", "description": "Clean production offcuts from extrusion and molding lines.", "public_summary": "DEMONSTRATION DATA: Clean plastic process scrap for recycling and pelletizing.", "sensitive_notes": "Exact resin grade and traceability are confidential.", "quantity": 1500.0, "unit": "tonnes", "location": "Bengaluru", "is_public": True},
        {"title": "Ground Granulated Blast Furnace Slag", "material_type": "Slag", "category": "construction", "organization_id": organizations[0].id, "owner_id": user_records[0].id, "status": "available", "description": "By-product from steelmaking used as cementitious supplement in concrete.", "public_summary": "DEMONSTRATION DATA: Slag for high-performance concrete and cement blending.", "sensitive_notes": "This is demonstration-only supply data and not a real industrial certification.", "quantity": 5400.0, "unit": "tonnes", "location": "Vizag", "is_public": False},
        {"title": "Wood Offcuts for Panel Feed", "material_type": "Wood waste", "category": "biomass", "organization_id": organizations[2].id, "owner_id": user_records[2].id, "status": "available", "description": "Offcuts and trimmed wood for chipboard or composite panel feedstock.", "public_summary": "DEMONSTRATION DATA: Wood offcuts recovered for secondary panel manufacturing.", "sensitive_notes": "Supplier-specific moisture and species composition remain privately stored.", "quantity": 920.0, "unit": "tonnes", "location": "Coimbatore", "is_public": True},
        {"title": "Copper Turnings", "material_type": "Copper scrap", "category": "metals", "organization_id": organizations[1].id, "owner_id": user_records[1].id, "status": "available", "description": "Turnings collected from machining operations for secondary metal recovery.", "public_summary": "DEMONSTRATION DATA: Copper-rich metal scrap suitable for refining and remelt.", "sensitive_notes": "Detailed alloy traceability and quality specs are limited.", "quantity": 510.0, "unit": "tonnes", "location": "Jaipur", "is_public": False},
        {"title": "Silica Fume", "material_type": "Silica fume", "category": "construction", "organization_id": organizations[0].id, "owner_id": user_records[0].id, "status": "available", "description": "Ultra-fine by-product from silicon metal processes for high-strength concrete.", "public_summary": "DEMONSTRATION DATA: Supplementary material beneficial for dense concrete applications.", "sensitive_notes": "Properties are estimated and not certification-grade.", "quantity": 480.0, "unit": "tonnes", "location": "Hyderabad", "is_public": True},
        {"title": "Mixed Plastic Regrind", "material_type": "Plastic production scrap", "category": "plastics", "organization_id": organizations[3].id, "owner_id": user_records[3].id, "status": "available", "description": "Mixed polymer regrind recovered from factory trimming and trimming rejects.", "public_summary": "DEMONSTRATION DATA: Regrind suitable for secondary plastic processing.", "sensitive_notes": "Resin mix and contamination controls are confidential.", "quantity": 1300.0, "unit": "tonnes", "location": "Bengaluru", "is_public": True},
        {"title": "Leather Trimming Waste", "material_type": "Leather waste", "category": "textiles", "organization_id": organizations[2].id, "owner_id": user_records[2].id, "status": "available", "description": "Trimmed leather waste suitable for soil conditioning and composite feedstock.", "public_summary": "DEMONSTRATION DATA: Secondary resource stream for composite and agricultural uses.", "sensitive_notes": "Private treatment and chemical content data remain restricted.", "quantity": 620.0, "unit": "tonnes", "location": "Chennai", "is_public": False},
        {"title": "Crusher Fines", "material_type": "Mineral fines", "category": "construction", "organization_id": organizations[0].id, "owner_id": user_records[0].id, "status": "available", "description": "Fine mineral aggregate recovered from crushing operations for fill and sub-base use.", "public_summary": "DEMONSTRATION DATA: Aggregate fines for civil fill and sub-base systems.", "sensitive_notes": "Exact grading and logistics details are private.", "quantity": 2400.0, "unit": "tonnes", "location": "Nagpur", "is_public": True},
        {"title": "Latex Foam Offcuts", "material_type": "Rubber waste", "category": "textiles", "organization_id": organizations[3].id, "owner_id": user_records[3].id, "status": "available", "description": "Foam offcuts from molded products for recycled rubber applications.", "public_summary": "DEMONSTRATION DATA: Foam waste stream for rubber recovery and composite filler use.", "sensitive_notes": "This is demonstration-only metadata and not a real certification record.", "quantity": 830.0, "unit": "tonnes", "location": "Bengaluru", "is_public": True},
        {"title": "Ceramic Tile Rejects", "material_type": "Ceramic waste", "category": "construction", "organization_id": organizations[0].id, "owner_id": user_records[0].id, "status": "available", "description": "Ceramic tile and sanitary rejects sorted for aggregate or filler reuse.", "public_summary": "DEMONSTRATION DATA: Ceramic rejects with reuse potential in aggregate systems.", "sensitive_notes": "Rejected units and quality distribution are restricted.", "quantity": 760.0, "unit": "tonnes", "location": "Hyderabad", "is_public": False},
        {"title": "Paper Mill Sludge", "material_type": "Paper sludge", "category": "biomass", "organization_id": organizations[2].id, "owner_id": user_records[2].id, "status": "available", "description": "Sludge recovered from recycled paper processing suitable for soil applications.", "public_summary": "DEMONSTRATION DATA: Fiber-rich sludge for land restoration and soil amendments.", "sensitive_notes": "Organic content and contamination diagnostics remain private.", "quantity": 1100.0, "unit": "tonnes", "location": "Mysuru", "is_public": True},
        {"title": "Tin Plating Sludge", "material_type": "Metal sludge", "category": "metals", "organization_id": organizations[1].id, "owner_id": user_records[1].id, "status": "available", "description": "Metal-rich sludge generated from plating operations with recoverable metals.", "public_summary": "DEMONSTRATION DATA: Metal-rich sludge for metallic recovery and environmental treatment.", "sensitive_notes": "Heavy metal screening and handling restrictions remain confidential.", "quantity": 690.0, "unit": "tonnes", "location": "Pune", "is_public": False},
        {"title": "HDPE Injection Molding Scrap", "material_type": "Plastic production scrap", "category": "plastics", "organization_id": organizations[3].id, "owner_id": user_records[3].id, "status": "available", "description": "Clean HDPE injection scrap from molded part manufacturing.", "public_summary": "DEMONSTRATION DATA: HDPE production scrap suitable for pelletization and remolding.", "sensitive_notes": "Exact resin quality and customer traceability are non-public.", "quantity": 1760.0, "unit": "tonnes", "location": "Bengaluru", "is_public": True},
    ]

    for material in materials:
        mapped = CITY_STATE.get(material["location"].strip().lower())
        if mapped:
            material["city"], material["state"] = mapped
            material["location"] = f"{mapped[0]}, {mapped[1]}"
        material["currency_code"] = "INR"
        material["price_unit"] = "INR/tonne"
        material["verification_status"] = "unverified"
        material["price_verification_status"] = "unverified"
        listing = MaterialListing(**material)
        db.add(listing)
    db.commit()

    all_listings = db.query(MaterialListing).all()
    for idx, listing in enumerate(all_listings):
        property_map = [
            ("SiO2", "36.8", "%", "Verified", "2026-01-15", "DEMONSTRATION DATA"),
            ("Moisture", "7.5", "%", "Company-declared", "2026-02-04", "Demo estimate by operator"),
            ("Bulk density", "1.2", "t/m3", "Estimated", "2026-03-10", "Assessed from production logs"),
            ("Heavy metals", "Below threshold", "mg/kg", "Missing", "2026-04-01", "Awaiting lab confirmation"),
        ]
        for name, value, unit, status, date, notes in property_map:
            db.add(
                MaterialProperty(
                    listing_id=listing.id,
                    name=name,
                    value=value,
                    unit=unit,
                    source="Company-declared" if status != "Verified" else "Verified",
                    status=status,
                    date=date,
                    notes=notes,
                )
            )
    db.commit()

    requirement_data = [
        {"user_id": user_records[1].id, "title": "Cement replacement material", "material_category": "Fly ash", "technical_specs": "Low moisture, cementitious, suitable for blended concrete", "quantity": 1500.0, "unit": "tonnes", "max_distance_km": 400, "location": "Hyderabad", "safety_constraints": "No hazardous contamination"},
        {"user_id": user_records[1].id, "title": "Biomass fuel feed", "material_category": "Sawdust", "technical_specs": "Dry and consistent calorific value", "quantity": 900.0, "unit": "tonnes", "max_distance_km": 240, "location": "Coimbatore", "safety_constraints": "Avoid excessive moisture"},
        {"user_id": user_records[1].id, "title": "Recycled plastic granulate", "material_category": "Plastic production scrap", "technical_specs": "Clean resin stream for pelletization", "quantity": 800.0, "unit": "tonnes", "max_distance_km": 300, "location": "Bengaluru", "safety_constraints": "No prohibited additives"},
    ]
    for item in requirement_data:
        mapped = CITY_STATE.get(item["location"].strip().lower())
        if mapped:
            item["city"], item["state"] = mapped
            item["location"] = f"{mapped[0]}, {mapped[1]}"
        db.add(BuyerRequirement(**item))
    db.commit()

    requirement_rows = db.query(BuyerRequirement).all()
    for idx, requirement in enumerate(requirement_rows):
        for listing in all_listings[: min(3, len(all_listings))]:
            score = 72 + idx * 8 + listing.id % 12
            db.add(
                MatchResult(
                    requirement_id=requirement.id,
                    listing_id=listing.id,
                    score=min(100, score),
                    reasons="Material category and quantity align with the requirement profile in this demonstration dataset.",
                    breakdown="Category fit; stock match; regional fit; price unavailable.",
                    warnings="This is a ranking aid, not an approval or compliance statement.",
                )
            )
    db.commit()

    access_request = AccessRequest(
        listing_id=all_listings[0].id,
        seeker_id=user_records[1].id,
        reason="Need detailed confidential specification data for a reuse feasibility review.",
        status="approved",
    )
    db.add(access_request)
    db.commit()

    for listing in all_listings[:3]:
        db.add(
            VerificationReview(
                listing_id=listing.id,
                reviewer_id=user_records[2].id,
                property_name="Material composition",
                status="reviewed",
                notes="DEMONSTRATION DATA: verification ready, awaiting formal evidence upload.",
                evidence_url="demo://lab-report.pdf",
            )
        )
    db.commit()

    for actor in user_records:
        log_event(db, actor.id, "seed_demo_data", "system", 0, "Seeded demonstration dataset for CircularMatch AI")


def seed_sourced_references(db: Session) -> None:
    """Insert source observations once; never overwrite existing user-maintained records."""
    retrieved_date = "2026-10-09"
    references = [
        {
            "slug": "india-fly-ash-generated-2024-25",
            "reference_type": "official_statistic",
            "name": "India fly ash generated",
            "value": 340,
            "qualifier": "over",
            "unit": "million tonnes",
            "reporting_period": "2024-25",
            "source_org": "Press Information Bureau, Government of India",
            "source_title": "India's Green Pathway: From Conservation to Climate Action",
            "source_url": "https://www.pib.gov.in/PressNoteDetails.aspx?ModuleId=3&NoteId=158047&lang=2&reg=3",
            "publication_date": "2026-04-07",
            "geographic_coverage": "India",
            "data_classification": "official_statistic",
            "verification_status": "verified",
            "methodology": "National figure reproduced from the cited PIB publication for FY 2024-25.",
            "limitations": "National total only; not a facility-level availability, quality, or supply record and not a material price.",
        },
        {
            "slug": "india-fly-ash-gainfully-used-2024-25",
            "reference_type": "official_statistic",
            "name": "India fly ash gainfully used",
            "value": 332.63,
            "unit": "million tonnes",
            "reporting_period": "2024-25",
            "source_org": "Press Information Bureau, Government of India",
            "source_title": "India's Green Pathway: From Conservation to Climate Action",
            "source_url": "https://www.pib.gov.in/PressNoteDetails.aspx?ModuleId=3&NoteId=158047&lang=2&reg=3",
            "publication_date": "2026-04-07",
            "geographic_coverage": "India",
            "data_classification": "official_statistic",
            "verification_status": "verified",
            "methodology": "National figure reproduced from the cited PIB publication for FY 2024-25.",
            "limitations": "National total only; not a facility-level availability, quality, or supply record and not a material price.",
        },
        {
            "slug": "hms-ii-scrap-reference-sep-2026",
            "reference_type": "market_reference",
            "name": "Scrap — HMS II",
            "value": 43810,
            "unit": "INR/tonne",
            "currency_code": "INR",
            "reporting_period": "September 2026",
            "source_org": "Ministry of Steel, Government of India (via Press Information Bureau)",
            "source_title": "India's Steel Sector Posts Steady Growth in H1 FY 2026-27",
            "source_url": "https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2319469&lang=2&reg=48",
            "publication_date": "2026-10-06",
            "geographic_coverage": "India, domestic raw material prices table",
            "material_grade": "HMS II",
            "data_classification": "market_reference",
            "verification_status": "verified",
            "methodology": "September 2026 value in the PIB Ministry of Steel table headed 'Domestic Raw Material Prices (₹/tonne)'.",
            "limitations": "Specific dated HMS II market reference only; not a supplier quotation or a price for steel by-products, fly ash, slag, or other materials. GST treatment is not stated.",
        },
        {
            "slug": "cea-grid-emission-factor-fy-2022-23",
            "reference_type": "environmental_factor_reference",
            "name": "Indian grid emission factor (including RES/captive injection)",
            "value": 0.716,
            "unit": "tCO2/MWh",
            "reporting_period": "FY 2022-23",
            "source_org": "Central Electricity Authority",
            "source_title": "CO2 Baseline Database for the Indian Power Sector — User Guide, Version 19.0",
            "source_url": "https://cea.nic.in/wp-content/uploads/baseline/2024/04/User_Guide__Version_19.0.pdf",
            "publication_date": None,
            "geographic_coverage": "India",
            "data_classification": "environmental_factor_reference",
            "verification_status": "source-claimed",
            "methodology": "The figure and RES/captive-injection scope were supplied in the request. The cited URL redirected to a CEA login page during retrieval; the document content could not be inspected. Not converted or loaded as a calculator factor.",
            "limitations": "Not independently verified; historical FY 2022-23 reporting period, not current for 2026. Not used in impact calculations.",
        },
        {
            "slug": "cpcb-ash-availability-portal-reference",
            "reference_type": "source_catalog",
            "name": "CPCB Ash Availability and Utilization Portal",
            "value": None,
            "unit": "no observation imported",
            "reporting_period": None,
            "source_org": "Central Pollution Control Board",
            "source_title": "Ash Availability and Utilization Portal",
            "source_url": "https://coalash.cpcb.gov.in/",
            "publication_date": None,
            "geographic_coverage": "India; portal reference only",
            "data_classification": "source_catalog",
            "verification_status": "missing",
            "methodology": "The portal is listed as a source reference; no facility-level observation was downloaded or imported.",
            "limitations": "No facility-level quantity, utilization, grade, or quality value is represented by this record.",
        },
        {
            "slug": "india-wpi-service-reference",
            "reference_type": "index_context",
            "name": "Wholesale Price Index service reference",
            "value": None,
            "unit": "index value unavailable",
            "reporting_period": None,
            "source_org": "Office of the Economic Adviser, Department for Promotion of Industry and Internal Trade, Government of India",
            "source_title": "Check Wholesale Price Index of Commodities",
            "source_url": "https://services.india.gov.in/service/detail/check-wholesale-price-index-of-commodities",
            "publication_date": None,
            "geographic_coverage": "India; series and month not retrieved",
            "data_classification": "index_context",
            "verification_status": "missing",
            "methodology": "No WPI series or monthly index observation was retrieved, so no numeric value is recorded.",
            "limitations": "An index is contextual data, not an absolute material selling price.",
        },
    ]
    for values in references:
        if db.query(SourcedReference).filter(SourcedReference.slug == values["slug"]).first() is None:
            db.add(SourcedReference(**values, retrieved_date=retrieved_date, last_updated=retrieved_date))
    db.commit()


with SessionLocal() as db:
    if db.query(User).count() == 0:
        seed_demo_data(db)
    seed_sourced_references(db)
