# CircularMatch AI

CircularMatch AI is a full-stack demo platform for discovering and evaluating industrial by-product reuse opportunities. It includes a FastAPI backend, a React + TypeScript + Tailwind frontend, and a persistent SQLite database with seeded demonstration data.

## Tech stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, Recharts
- Backend: FastAPI, SQLAlchemy, SQLite
- Auth: JWT, PBKDF2 password hashing
- Testing: Pytest
- Locale and currency: `en-IN`, INR, and metric mass units

## Demo credentials

- Producer: username `producer1`, password `demo123`
- Seeker: username `seeker1`, password `demo123`
- Verifier: username `verifier1`, password `demo123`
- Administrator: username `admin`, password `demo123`

## Quick start

1. Create and activate the Python virtual environment:

   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

2. Install backend dependencies:

   ```bash
   pip install -r backend/requirements.txt
   ```

3. Install frontend dependencies:

   ```bash
   cd frontend
   npm install
   ```

4. Start the backend:

   ```bash
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. Start the frontend:

   ```bash
   cd frontend
   npm run dev -- --host 0.0.0.0 --port 5173
   ```

6. Open `http://localhost:5173` to use the app.

## Notes

- The seeded records are clearly marked as demonstration data and must not be treated as real-world certifications or verified claims.
- Demo materials do not contain seller prices. Empty prices are shown as “Price unavailable — request a supplier quotation”.
- Legacy price amounts are preserved, tagged with currency code `UNK`, and hidden from INR price displays until their original currency and provenance are confirmed. No currency conversion is applied.
- New material prices are stored as INR per tonne. GST rate and inclusive/exclusive treatment are separate and remain unspecified unless entered.
- Emission calculations use no built-in estimates. A net result requires verified factor records with source, reporting year, units, assumptions, and methodology; incomplete results are labelled “Insufficient data”.
- Additive schema migrations retain existing rows and values.
- All role-based authorization checks are enforced in the backend API.
- Restricted material fields and confidential documents require an approved access request before being returned.

## Automated tests

Run:

```bash
cd backend
.\..\.venv\Scripts\python.exe -m pytest -q
```

## Data model and workflow summary

- Producers publish materials and approve or deny access requests.
- Seekers submit requirements and receive explainable matching recommendations.
- Verifiers review metadata, evidence, and claims.
- Administrators review all actions and audit events.
- Environmental and economic benefits are computed using configurable documented assumptions.

## Indian market data and source status

The legacy seed organizations and all 20 sample material listings in the existing SQLite database are fictional **DEMONSTRATION DATA**, not real supplier records. Existing listing records and legacy amounts are preserved; unknown-currency amounts remain `UNK` and are not displayed as INR. Freshly seeded demo listings have no fabricated prices. Sourced references below are separate national/reference observations, not individual company listings.

Source retrieval and checks were performed on **9 October 2026**:

| Record | Value and period | Source and publication date | Status and limitations |
| --- | --- | --- | --- |
| India fly ash generated | Over 340 million tonnes, FY 2024–25 | PIB, “India's Green Pathway: From Conservation to Climate Action,” 7 April 2026. [Source](https://www.pib.gov.in/PressNoteDetails.aspx?ModuleId=3&NoteId=158047&lang=2&reg=3) | **Verified against retrieved PIB page.** National total, not facility availability, quality, or price. |
| India fly ash gainfully used | 332.63 million tonnes, FY 2024–25 | Same PIB source, 7 April 2026. [Source](https://www.pib.gov.in/PressNoteDetails.aspx?ModuleId=3&NoteId=158047&lang=2&reg=3) | **Verified against retrieved PIB page.** National total only. |
| Scrap — HMS II | ₹43,810/tonne, September 2026 | Ministry of Steel via PIB, “India's Steel Sector Posts Steady Growth in H1 FY 2026-27,” 6 October 2026. The figure is in “Domestic Raw Material Prices (₹/tonne).” [Source](https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2319469&lang=2&reg=48) | **Verified against retrieved PIB page.** Dated HMS II market reference only; not a quote for all scrap or any by-product. GST treatment is unstated. |
| Indian grid emission factor including RES/captive injection | 0.716 tCO₂/MWh, FY 2022–23 | CEA, *CO₂ Baseline Database for the Indian Power Sector — User Guide, Version 19.0*. [Cited source](https://cea.nic.in/wp-content/uploads/baseline/2024/04/User_Guide__Version_19.0.pdf) | **Source-claimed, not independently verified.** The cited URL redirected to a CEA login page. Stored as a source reference only, not used as a calculator factor; historical reporting period, not current for 2026. |
| CPCB Ash Availability and Utilization Portal | No facility-level observation imported | [CPCB portal](https://coalash.cpcb.gov.in/) | **Missing.** Portal is listed as a source, but no facility record was downloaded. The national PIB totals are not attributed to a factory. |
| Wholesale Price Index context | No index observation imported | OEA / Government of India, “Check Wholesale Price Index of Commodities.” [Service](https://services.india.gov.in/service/detail/check-wholesale-price-index-of-commodities) | **Missing.** No month, series, or index value was retrieved. WPI is contextual index data, not an absolute selling price. |

These records are seeded idempotently into `sourced_references`; no existing organization or listing is deleted or relabelled. Data Sources & Methodology cards appear on the dashboard and impact calculator. The existing demo listings are: Fly Ash Cement Blend; Rice Husk Ash Pozzolan; Aluminium Scrap Extrusions; Steel Scrap Bundles; Clean Sawdust Biomass; Textile Waste for Fiber Recovery; Glass Cullet; Plastic Process Scrap; Ground Granulated Blast Furnace Slag; Wood Offcuts for Panel Feed; Copper Turnings; Silica Fume; Mixed Plastic Regrind; Leather Trimming Waste; Crusher Fines; Latex Foam Offcuts; Ceramic Tile Rejects; Paper Mill Sludge; Tin Plating Sludge; and HDPE Injection Molding Scrap.

Marketplace filters include state, city, category, price availability, and verification status. The current city/state examples are Indian demo locations (including Hyderabad, Telangana; Pune, Maharashtra; Coimbatore, Tamil Nadu; Bengaluru, Karnataka; and Visakhapatnam, Andhra Pradesh); their presence is not a claim of real supply.

## Data APIs

- `GET /api/marketplace?state=Telangana&city=Hyderabad&category=construction&price_available=false&verification_status=unverified` filters listings.
- Supplier prices are stored as INR/tonne with source, validity date/status, GST treatment, and verification status. Authorized producers can update prices only on their own non-demonstration listings using `PUT /api/materials/{listing_id}/price`; admins can update any non-demonstration listing. Expired, unknown-currency, and demonstration amounts are not presented as valid supplier prices.
- Seekers can submit quotation requests with quantity, unit, delivery location, and optional message using `POST /api/quotation-requests`; `GET /api/quotation-requests` returns only the caller's requests, the supplier's organization requests, or all requests for admins.
- Listings without a valid INR price retain “Price unavailable — request a supplier quotation” and expose a request form on Marketplace and Matches. The success message appears only after the persisted API request is confirmed.
- Material prices carry explicit currency/unit, GST treatment, source organization/title/URL, publication/retrieval dates, geographic scope, grade, type, limitations, validity, verification status, and last-updated date.
- `GET /api/emission-factors` lists sourced factor records. Administrators can add records with `POST /api/emission-factors`; factors must be marked verified to be used in the calculator.
- `GET /api/data-sources` returns traceable national statistics, market references, and explicit missing/source-claimed records with their sources, dates, coverage, methodology, and limitations.
- `/api/calculator` accepts tonnes or kg, references factor records by ID, reports transport/processing/avoided-disposal/substitution separately, and reports monetary inputs/results only in INR.

## Frontend formatting tests

```bash
cd frontend
npm test
```
