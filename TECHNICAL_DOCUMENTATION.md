# RapidScan AI — Technical Documentation

**Portfolio-ready technical overview for recruiters and technical reviewers.**

---

## 1. Project Overview

**RapidScan AI** is an AI-powered chest X-ray triage system built for rural and resource-limited hospitals. It helps clinicians prioritize which studies need urgent radiology review by combining:

- **Computer vision** — Detects findings (e.g. pneumothorax, effusion, consolidation) from the image.
- **LLM reasoning** — Produces an urgency score (1–10), clinical reasoning, recommended action, and risk factors.
- **Hybrid RAG** — Uses institutional “hospital memory” (similar past cases) and patient-specific history so the same finding can receive different urgency based on context.

The system exposes a REST API consumed by a React frontend with Google Auth; multiple facilities (hospitals) can use it, each with their own queue.

---

## 2. Problem & Solution

| Problem | Solution |
|--------|----------|
| Rural hospitals have limited radiologist capacity and need to prioritize studies. | Automated triage ranks studies by urgency and explains why. |
| Rule-based triage (e.g. “pneumothorax = 10”) ignores context. | Gemini LLM + RAG use similar past cases and patient history for context-aware urgency. |
| No shared “institutional memory” of how similar cases were handled. | Weaviate stores hospital cases and patient records; every new upload enriches RAG for future triage. |

---

## 3. Tech Stack

| Layer | Technology | Role |
|-------|------------|------|
| **API** | Flask (Python 3.9+) | REST API, CORS, file upload, static file serving. |
| **Database** | SQLite | Facilities, scans, patients; migrations for schema evolution. |
| **Vision** | torchxrayvision (DenseNet121) | Pre-trained chest X-ray model; 18+ pathologies, confidence scores. |
| **LLM** | Google Gemini (e.g. gemini-2.0-flash) | Urgency, reasoning, recommended action, risk factors; fallback to rule-based on failure. |
| **RAG** | Weaviate | Two collections: HospitalCases (BM25), PatientRecords (by patient_id); seeded + updated on each upload. |
| **Deploy** | Docker, Render | Dockerfile + docker-compose for Weaviate; render.yaml for backend. |
| **Frontend** | React, Google Auth | Upload, queue view, scan detail; facility-scoped queues. |

---

## 4. System Architecture

```
┌─────────────┐     POST /upload      ┌──────────────────────────────────────────────────┐
│   Frontend  │ ───────────────────► │  Flask API (app.py)                              │
│   (React)   │     GET /queue,       │  • Validate file, resolve facility & patient     │
│             │     GET /scan/<id>    │  • Save image → run model → call LLM with RAG     │
└─────────────┘                       │  • Persist scan (SQLite) → update RAG (Weaviate)  │
                                     │  • Return 13-field JSON                            │
                                     └───────────────┬────────────────────────────────────┘
                                                     │
         ┌───────────────────────────────────────────┼───────────────────────────────────┐
         │                                           │                                     │
         ▼                                           ▼                                     ▼
┌─────────────────┐                    ┌─────────────────────┐              ┌─────────────────────┐
│  SQLite         │                    │  torchxrayvision     │              │  Weaviate            │
│  • facilities   │                    │  DenseNet121         │              │  • HospitalCases      │
│  • scans        │                    │  (condition list +  │              │  • PatientRecords     │
│  • patients     │                    │   confidence)        │              │  BM25 + filters       │
└─────────────────┘                    └──────────┬──────────┘              └──────────┬──────────┘
                                                  │                                      │
                                                  ▼                                      ▼
                                     ┌─────────────────────┐              ┌─────────────────────┐
                                     │  Google Gemini      │              │  Hybrid RAG prompt   │
                                     │  (urgency, reasoning│              │  (similar cases +   │
                                     │   action, risks)    │              │   patient history)  │
                                     └─────────────────────┘              └─────────────────────┘
```

---

## 5. Key Components

### 5.1 Backend (Flask)

- **app.py** — Routes: health, GET/POST `/facilities`, upload, queue, scan detail, scan status, stats, admin (seed Weaviate, weaviate-stats, clear-queue). Normalizes all scan responses to a 13-field contract; handles file upload and patient create/update.
- **database.py** — SQLite: init, migrations (LLM fields, patients table, patient profile fields), facilities (get/add), scans (add, queue, get, stats), patients (get_or_create, update_scan_count, get_patient_info), clear_all_scans.
- **xray_model.py** — Loads torchxrayvision DenseNet121; preprocesses image (grayscale, 224×224, normalize); runs inference; maps pathologies to urgency; exposes `predict`, `predict_with_reasoning`, `predict_with_hybrid_rag`.
- **llm_triage.py** — Gemini client; builds prompts with findings, facility, queue length; optional RAG sections (hospital cases + patient history); parses JSON response; fallback urgency on API/parse error.
- **weaviate_store.py** — Connects to Weaviate; maintains HospitalCases and PatientRecords; `add_scan_to_rag` (normalizes conditions to strings), `find_similar_hospital_cases` (BM25), `get_patient_history` (merge multiple records); seed from static data; every upload adds one case and optionally one patient record.

### 5.2 Data Stores

- **SQLite** — Single file (`xray_triage.db`). Tables: `facilities` (id, name, location), `scans` (id, facility_id, patient_id, urgency_score, conditions JSON, reasoning, recommended_action, risk_factors, ai_confidence, timestamps, paths), `patients` (id, patient_identifier, name, age, gender, blood_type, medical_notes, total_scans, dates). Migrations run on app init.
- **Weaviate** — Two collections, no vectorizer (keyword/BM25). HospitalCases: case_id, conditions[], urgency_score, outcome, clinical_notes, content (for search). PatientRecords: patient_id, age, gender, risk_factors[], scan_history (JSON string), total_previous_scans. New facilities created via API; new hospital/patient data added on each upload.

### 5.3 API Contract (Scan Response)

All scan-bearing endpoints return the same 13 fields: `scan_id`, `patient_id`, `patient_name`, `patient_age`, `patient_blood_type`, `patient_medical_file`, `facility_id`, `conditions_detected`, `urgency_ranking`, `confidence_score`, `gemini_reasoning`, `timestamp`, `image_url`. Patient fields are null when no patient is linked.

---

## 6. RAG Design (Hybrid)

- **HospitalCases** — Curated seed (e.g. 15 cases) plus one new case per upload. BM25 search over conditions/outcome/clinical_notes retrieves up to 3 similar cases for the LLM prompt. Gives “institutional memory” (how similar cases were handled).
- **PatientRecords** — Seed (e.g. 12 patients) plus one new record per upload when `patient_id` is sent. Lookup by `patient_id`; multiple records per patient are merged (combined scan_history, latest demographics, union of risk_factors). Enables “same finding, different urgency” for high-risk vs low-risk patients.
- Conditions from the model are passed as list of dicts `[{name, confidence}]`; RAG layer normalizes to list of strings for Weaviate TEXT_ARRAY and for `join()` in content strings.

---

## 7. Security & Configuration

- **Secrets** — `GEMINI_API_KEY` (and optional `GEMINI_MODEL`) in `.env`; `.env` is gitignored; `.env.example` documents required and optional variables.
- **CORS** — Allow-all by default for hackathon/development; optional `ALLOWED_ORIGINS` for production.
- **Upload** — Max 10 MB; allowed types jpg, jpeg, png. Files stored under `uploads/` with unique names.
- **Auth** — No backend authentication; frontend uses Google Auth and sends `facility_id` to scope uploads and queue.

---

## 8. Deployment

- **Local** — `python app.py` (default port 5001). Weaviate: `docker compose -f docker-compose-weaviate.yml up -d`; seed once via `POST /admin/seed-weaviate`.
- **Render** — `render.yaml` defines a web service: build `pip install -r requirements.txt`, start `python app.py`, env `GEMINI_API_KEY` (secret), `PORT`. Weaviate would need a separate hosted instance or optional RAG disable for serverless-style deploy.
- **Docker** — `Dockerfile` and `.dockerignore` present for containerized backend.

---

## 9. Testing

- **test_backend.py** — DB init, dummy image, model inference, add_scan, get_queue, get_scan, get_stats, update_scan_status (no server).
- **test_llm_triage.py** — Four scenarios (critical/moderate/normal/multiple conditions); requires `GEMINI_API_KEY`; fallback when quota exceeded.
- **test_hybrid_rag.py** — Weaviate connection, seed, hospital BM25 query, patient history, hybrid reasoning; optional API tests (upload, upload-updates-RAG) with server running.
- **test_api.py** — Integration tests for health, upload, queue, scan, stats, status update (server required).

---

## 10. Technical Highlights (Portfolio Talking Points)

- **Hybrid RAG** — Two-level context (institutional + patient) with Weaviate; BM25 and key-value style lookups; merge logic for multiple records per patient.
- **Graceful degradation** — Missing Gemini key or quota → rule-based urgency; Weaviate down → RAG update logged, upload still succeeds; conditions normalized so dicts from model don’t break RAG writes.
- **Multi-tenant ready** — Dynamic facilities (GET/POST); facility-scoped queue and upload; frontend can map Google Auth to facility_id.
- **Structured API** — Single 13-field scan contract across upload, queue, and scan detail; patient profile (name, age, blood type, medical notes) in DB and responses.
- **Production touches** — Migrations for schema evolution, `.env.example`, Docker and Render config, CORS and upload limits, clear separation of model / LLM / RAG / DB layers.

---

*This document is intended for portfolio and technical review. For full endpoint list and internal status, see [STATUS.md](../STATUS.md) in the repo.*
