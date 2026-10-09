import os
from datetime import date, timedelta

os.environ["DATABASE_URL"] = "sqlite://"

from fastapi.testclient import TestClient

from app.main import SessionLocal, app, seed_sourced_references
from app.models import SourcedReference

client = TestClient(app)


def auth_headers(username: str, password: str):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_login_success():
    response = client.post("/api/auth/login", json={"username": "producer1", "password": "demo123"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["username"] == "producer1"
    assert "token" in payload


def test_private_listing_is_restricted_without_permission():
    seeker_login = client.post("/api/auth/login", json={"username": "seeker1", "password": "demo123"})
    seeker_headers = {"Authorization": f"Bearer {seeker_login.json()['token']}"}
    admin_headers = auth_headers("admin", "demo123")
    response = client.get("/api/materials", headers=admin_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    seeker_id = seeker_login.json()["user"]["id"]
    private_item = next((item for item in items if not item["is_public"] and item["owner_id"] != seeker_id), None)
    assert private_item is not None
    detail = client.get(f"/api/materials/{private_item['id']}", headers=seeker_headers)
    assert detail.status_code == 200
    body = detail.json()["item"]
    assert "Access restricted" in body["sensitive_notes"]


def test_access_request_and_approval_flow():
    seeker_login = client.post("/api/auth/login", json={"username": "seeker1", "password": "demo123"})
    seeker_headers = {"Authorization": f"Bearer {seeker_login.json()['token']}"}
    producer_headers = auth_headers("producer1", "demo123")
    admin_headers = auth_headers("admin", "demo123")
    response = client.get("/api/materials", headers=admin_headers)
    seeker_id = seeker_login.json()["user"]["id"]
    private_item = next((item for item in response.json()["items"] if not item["is_public"] and item["owner_id"] != seeker_id), None)
    assert private_item is not None
    request_response = client.post(
        "/api/access-requests",
        headers=seeker_headers,
        json={"listing_id": private_item["id"], "reason": "Need material composition for evaluation."},
    )
    assert request_response.status_code == 201
    request_id = request_response.json()["item"]["id"]
    decision = client.post(
        f"/api/access-requests/{request_id}/decision",
        headers=producer_headers,
        json={"decision": "approved"},
    )
    assert decision.status_code == 200
    detail = client.get(f"/api/materials/{private_item['id']}", headers=seeker_headers)
    assert detail.status_code == 200
    assert "Access restricted" not in detail.json()["item"]["sensitive_notes"]


def test_requirement_matching_and_calculator():
    seeker_headers = auth_headers("seeker1", "demo123")
    requirement = client.post(
        "/api/requirements",
        headers=seeker_headers,
        json={
            "title": "Commercial plastic feedstock",
            "material_category": "Plastic production scrap",
            "quantity": 500,
            "location": "Bengaluru",
            "technical_specs": "Clean and consistent resin stream",
        },
    )
    assert requirement.status_code == 201
    requirement_id = requirement.json()["item"]["id"]

    matches = client.post(
        "/api/matches",
        headers=seeker_headers,
        json={"requirement_id": requirement_id},
    )
    assert matches.status_code == 200
    data = matches.json()
    assert len(data["items"]) >= 1
    assert data["items"][0]["score"] > 0

    result = client.post(
        "/api/calculator",
        headers=seeker_headers,
        json={"material_type": "Fly ash", "mass_tonnes": 100, "distance_km": 50},
    )
    assert result.status_code == 200
    assert result.json()["status"] == "insufficient_data"
    assert result.json()["result"]["net_emissions_benefit_kgco2e"] is None
    assert result.json()["result"]["net_economic_benefit_inr"] is None


def test_price_metadata_is_explicit_and_missing_prices_stay_unavailable():
    headers = auth_headers("admin", "demo123")
    items = client.get("/api/marketplace", headers=headers).json()["items"]
    demo_item = next(item for item in items if item["demo_label"] == "DEMONSTRATION DATA")
    assert all(not item["price_available"] for item in items if item["demo_label"] == "DEMONSTRATION DATA")
    assert all(
        prop["status"] == "Unverified" and prop["source"] == "Demonstration data"
        for item in items
        if item["demo_label"] == "DEMONSTRATION DATA"
        for prop in item["properties"]
    )
    assert demo_item["price_available"] is False
    assert demo_item["price_per_ton"] is None
    assert demo_item["currency_code"] == "INR"
    assert demo_item["price_unit"] == "INR/tonne"

    invalid_index = client.post(
        "/api/materials",
        headers=headers,
        json={
            "title": "Index must not be absolute price",
            "material_type": "Steel scrap",
            "category": "metals",
            "quantity": 1,
            "unit": "tonnes",
            "city": "Hyderabad",
            "state": "Telangana",
            "price_per_tonne": 125000,
            "price_type": "index",
        },
    )
    assert invalid_index.status_code == 400


def test_sourced_india_references_keep_scope_metadata_and_verification_status():
    response = client.get("/api/data-sources")
    assert response.status_code == 200
    records = {item["slug"]: item for item in response.json()["items"]}

    generated = records["india-fly-ash-generated-2024-25"]
    assert generated["value"] == 340
    assert generated["qualifier"] == "over"
    assert generated["unit"] == "million tonnes"
    assert generated["reporting_period"] == "2024-25"
    assert generated["geographic_coverage"] == "India"
    assert generated["source_url"].startswith("https://www.pib.gov.in/")
    assert generated["publication_date"] == "2026-04-07"
    assert generated["retrieved_date"] == "2026-10-09"
    assert generated["verification_status"] == "verified"
    assert "not a facility-level" in generated["limitations"]

    used = records["india-fly-ash-gainfully-used-2024-25"]
    assert used["value"] == 332.63
    assert used["unit"] == "million tonnes"
    assert used["reporting_period"] == "2024-25"
    assert used["verification_status"] == "verified"

    scrap = records["hms-ii-scrap-reference-sep-2026"]
    assert scrap["value"] == 43810
    assert scrap["currency_code"] == "INR"
    assert scrap["unit"] == "INR/tonne"
    assert scrap["reporting_period"] == "September 2026"
    assert scrap["material_grade"] == "HMS II"
    assert scrap["data_classification"] == "market_reference"
    assert scrap["publication_date"] == "2026-10-06"
    assert "not a supplier quotation" in scrap["limitations"]

    cea = records["cea-grid-emission-factor-fy-2022-23"]
    assert cea["value"] == 0.716
    assert cea["unit"] == "tCO2/MWh"
    assert cea["reporting_period"] == "FY 2022-23"
    assert cea["verification_status"] == "source-claimed"
    assert "not used in impact calculations" in cea["limitations"].lower()
    factors = client.get("/api/emission-factors", headers=auth_headers("admin", "demo123")).json()["items"]
    assert all("CEA" not in factor["name"] for factor in factors)

    wpi = records["india-wpi-service-reference"]
    assert wpi["value"] is None
    assert wpi["verification_status"] == "missing"
    assert "not an absolute material selling price" in wpi["limitations"]

    cpcb = records["cpcb-ash-availability-portal-reference"]
    assert cpcb["value"] is None
    assert cpcb["verification_status"] == "missing"
    assert "no facility-level" in cpcb["limitations"].lower()


def test_sourced_reference_seed_is_idempotent():
    with SessionLocal() as db:
        initial_count = db.query(SourcedReference).count()
        seed_sourced_references(db)
        seed_sourced_references(db)
        assert db.query(SourcedReference).count() == initial_count


def test_inr_quote_persists_source_dates_gst_and_coverage():
    headers = auth_headers("producer1", "demo123")
    response = client.post(
        "/api/materials",
        headers=headers,
        json={
            "title": "Supplier quote metadata test",
            "material_type": "Steel scrap",
            "category": "metals",
            "quantity": 5,
            "unit": "tonnes",
            "city": "Pune",
            "state": "Maharashtra",
            "price_per_tonne": 125000,
            "currency_code": "INR",
            "price_original_amount": 125,
            "price_original_currency_code": "INR",
            "price_original_unit": "INR/kg",
            "price_type": "market_quote",
            "price_source_org": "Test supplier",
            "price_source_title": "Test supplier quotation",
            "price_source_url": "https://example.org/quote",
            "price_publication_date": "2026-10-01",
            "price_retrieved_date": "2026-10-09",
            "price_valid_until": (date.today() + timedelta(days=30)).isoformat(),
            "price_geographic_coverage": "Pune",
            "price_grade": "Test grade",
            "gst_rate_percent": 18,
            "gst_inclusive": False,
        },
    )
    assert response.status_code == 201, response.text
    listing = response.json()["item"]
    assert listing["price_per_ton"] == 125000
    assert listing["currency_code"] == "INR"
    assert listing["price_unit"] == "INR/tonne"
    assert listing["price_original_amount"] == 125
    assert listing["price_original_currency_code"] == "INR"
    assert listing["price_original_unit"] == "INR/kg"
    assert listing["price_type"] == "market_quote"
    assert listing["price_source_title"] == "Test supplier quotation"
    assert listing["price_publication_date"] == "2026-10-01"
    assert listing["price_retrieved_date"] == "2026-10-09"
    assert listing["price_geographic_coverage"] == "Pune"
    assert listing["gst_rate_percent"] == 18
    assert listing["gst_inclusive"] is False
    assert listing["price_verification_status"] == "unverified"
    assert listing["price_status"] == "valid"
    assert listing["price_valid_until"] == (date.today() + timedelta(days=30)).isoformat()
    assert listing["price_available"] is True


def create_supplier_listing(headers, title="Quotation test material"):
    response = client.post(
        "/api/materials",
        headers=headers,
        json={
            "title": title,
            "material_type": "Industrial by-product",
            "category": "construction",
            "quantity": 4,
            "unit": "tonnes",
            "city": "Hyderabad",
            "state": "Telangana",
            "public_summary": "Supplier-created listing for quotation workflow testing.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["item"]


def test_supplier_can_save_an_inr_price_and_only_owner_or_admin_can_change_it():
    producer_headers = auth_headers("producer1", "demo123")
    seeker_headers = auth_headers("seeker1", "demo123")
    listing = create_supplier_listing(producer_headers)
    expiry = (date.today() + timedelta(days=30)).isoformat()
    payload = {
        "price_per_tonne": 4500,
        "currency_code": "INR",
        "price_source_org": "Supplier entered quotation",
        "price_valid_until": expiry,
    }

    forbidden = client.put(f"/api/materials/{listing['id']}/price", headers=seeker_headers, json=payload)
    assert forbidden.status_code == 403

    saved = client.put(f"/api/materials/{listing['id']}/price", headers=producer_headers, json=payload)
    assert saved.status_code == 200, saved.text
    item = saved.json()["item"]
    assert item["price_per_ton"] == 4500
    assert item["currency_code"] == "INR"
    assert item["price_unit"] == "INR/tonne"
    assert item["price_available"] is True
    assert item["price_valid_until"] == expiry
    assert item["price_status"] == "valid"
    assert item["price_verification_status"] == "unverified"
    assert item["price_type"] == "supplier_quote"

    marketplace = client.get(
        "/api/marketplace?price_available=true",
        headers=seeker_headers,
    )
    assert marketplace.status_code == 200
    updated_listing = next(row for row in marketplace.json()["items"] if row["id"] == listing["id"])
    assert updated_listing["price_per_ton"] == 4500
    assert updated_listing["price_available"] is True

    admin_listing = create_supplier_listing(producer_headers, "Admin price update test")
    admin_saved = client.put(
        f"/api/materials/{admin_listing['id']}/price",
        headers=auth_headers("admin", "demo123"),
        json={**payload, "price_per_tonne": 4600},
    )
    assert admin_saved.status_code == 200, admin_saved.text
    assert admin_saved.json()["item"]["price_per_ton"] == 4600


def test_expired_currency_unknown_and_demo_prices_are_not_published():
    producer_headers = auth_headers("producer1", "demo123")
    admin_headers = auth_headers("admin", "demo123")
    seeker_headers = auth_headers("seeker1", "demo123")
    listing = create_supplier_listing(producer_headers, "Price validity test material")

    invalid_currency = client.put(
        f"/api/materials/{listing['id']}/price",
        headers=producer_headers,
        json={
            "price_per_tonne": 4500,
            "currency_code": "USD",
            "price_source_org": "Supplier",
            "price_valid_until": (date.today() + timedelta(days=1)).isoformat(),
        },
    )
    assert invalid_currency.status_code == 400

    expired = client.put(
        f"/api/materials/{listing['id']}/price",
        headers=producer_headers,
        json={
            "price_per_tonne": 4500,
            "currency_code": "INR",
            "price_source_org": "Supplier",
            "price_valid_until": (date.today() - timedelta(days=1)).isoformat(),
        },
    )
    assert expired.status_code == 400

    demo_listing = next(
        row for row in client.get("/api/materials", headers=admin_headers).json()["items"]
        if row["demo_label"] == "DEMONSTRATION DATA"
    )
    demo_attempt = client.put(
        f"/api/materials/{demo_listing['id']}/price",
        headers=admin_headers,
        json={
            "price_per_tonne": 4500,
            "currency_code": "INR",
            "price_source_org": "Supplier",
            "price_valid_until": (date.today() + timedelta(days=30)).isoformat(),
        },
    )
    assert demo_attempt.status_code == 400
    demo_after = client.get(f"/api/materials/{demo_listing['id']}", headers=seeker_headers).json()["item"]
    assert demo_after["price_available"] is False
    assert demo_after["price_per_ton"] is None


def test_supplier_quotation_request_is_persisted_and_visible_to_buyer_and_supplier():
    producer_headers = auth_headers("producer1", "demo123")
    seeker_headers = auth_headers("seeker1", "demo123")
    listing = create_supplier_listing(producer_headers, "Missing quote request material")
    response = client.post(
        "/api/quotation-requests",
        headers=seeker_headers,
        json={
            "listing_id": listing["id"],
            "requested_quantity": 2500,
            "quantity_unit": "kg",
            "delivery_location": "Hyderabad, Telangana",
            "message": "Please include lead time.",
        },
    )
    assert response.status_code == 201, response.text
    saved = response.json()["item"]
    assert saved["status"] == "pending"
    assert saved["listing_id"] == listing["id"]
    assert saved["requested_quantity"] == 2500
    assert saved["quantity_unit"] == "kg"
    assert saved["delivery_location"] == "Hyderabad, Telangana"
    assert saved["message"] == "Please include lead time."

    buyer_requests = client.get("/api/quotation-requests", headers=seeker_headers)
    assert buyer_requests.status_code == 200
    assert any(row["id"] == saved["id"] for row in buyer_requests.json()["items"])
    supplier_requests = client.get("/api/quotation-requests", headers=producer_headers)
    assert supplier_requests.status_code == 200
    assert any(row["id"] == saved["id"] for row in supplier_requests.json()["items"])


def test_listing_and_requirement_match_convert_kg_to_tonnes():
    producer_headers = auth_headers("producer1", "demo123")
    seeker_headers = auth_headers("seeker1", "demo123")
    listing = client.post(
        "/api/materials",
        headers=producer_headers,
        json={
            "title": "Test fly ash kg conversion",
            "material_type": "Fly ash",
            "category": "construction",
            "quantity": 1000,
            "unit": "kg",
            "city": "Hyderabad",
            "state": "Telangana",
            "public_summary": "Test-only listing",
        },
    )
    assert listing.status_code == 201, listing.text
    listing_id = listing.json()["item"]["id"]
    assert listing.json()["item"]["currency_code"] == "INR"
    assert listing.json()["item"]["city"] == "Hyderabad"

    requirement = client.post(
        "/api/requirements",
        headers=seeker_headers,
        json={
            "title": "Test tonne requirement",
            "material_category": "Fly ash",
            "quantity": 1,
            "unit": "tonnes",
            "city": "Hyderabad",
            "state": "Telangana",
        },
    )
    assert requirement.status_code == 201
    matches = client.post(
        "/api/matches",
        headers=seeker_headers,
        json={"requirement_id": requirement.json()["item"]["id"]},
    )
    matching_row = next(item for item in matches.json()["items"] if item["listing_id"] == listing_id)
    assert "Quantity compatibility" in matching_row["breakdown"]


def test_emissions_require_verified_sourced_factors_and_keep_components_separate():
    admin_headers = auth_headers("admin", "demo123")
    seeker_headers = auth_headers("seeker1", "demo123")
    values = {
        "transport": ("kgCO2e/tonne-km", 2.0),
        "processing": ("kgCO2e/tonne", 3.0),
        "avoided_disposal": ("kgCO2e/tonne", 5.0),
        "virgin_substitution": ("kgCO2e/tonne", 10.0),
    }
    factor_ids = {}
    for factor_type, (unit, value) in values.items():
        response = client.post(
            "/api/emission-factors",
            headers=admin_headers,
            json={
                "factor_type": factor_type,
                "name": f"Test {factor_type} factor",
                "value": value,
                "unit": unit,
                "source_org": "Test source",
                "source_title": "Test-only factor source",
                "source_url": "https://example.org/test-factor",
                "retrieved_date": "2026-10-09",
                "geographic_coverage": "Test scope",
                "reporting_year": 2025,
                "assumptions": "Test fixture only",
                "methodology": "Test calculation",
                "verification_status": "verified",
                "limitations": "Not real-world data",
            },
        )
        assert response.status_code == 201
        factor = response.json()["item"]
        assert factor["source_title"] == "Test-only factor source"
        assert factor["reporting_year"] == 2025
        factor_ids[factor_type] = factor["id"]

    response = client.post(
        "/api/calculator",
        headers=seeker_headers,
        json={
            "mass": 1000,
            "mass_unit": "kg",
            "distance_km": 10,
            "factor_ids": factor_ids,
            "transport_cost_inr_per_tonne_km": 2,
            "processing_cost_inr_per_tonne": 3,
            "avoided_disposal_savings_inr_per_tonne": 5,
            "material_purchase_cost_inr_per_tonne": 8,
        },
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["mass_tonnes"] == 1
    assert result["transport_emissions_kgco2e"] == 20
    assert result["processing_emissions_kgco2e"] == 3
    assert result["avoided_disposal_kgco2e"] == 5
    assert result["virgin_substitution_kgco2e"] == 10
    assert result["net_emissions_benefit_kgco2e"] == -8
    assert result["net_economic_benefit_inr"] == -26
    assert result["currency_code"] == "INR"
    assert result["reporting_years"] == [2025]
