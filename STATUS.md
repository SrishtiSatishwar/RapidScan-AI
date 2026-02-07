# Project Status: Rural Hospital AI Radiology Triage – Backend

**Last updated:** Dynamic facilities (GET/POST /facilities); DB grows with new hospitals; frontend/Google Auth can list and create facilities.

---

## At a glance

| Layer | Technology | Purpose |
|-------|------------|---------|
| **API** | Flask, CORS | 11 routes: health, **GET/POST /facilities**, upload, queue, scan, scan status, stats, seed-weaviate, weaviate-stats, clear-queue. Static uploads/heatmaps. |
| **DB** | SQLite (xray_triage.db) | **facilities** (3 seeded; more via POST /facilities — one per hospital/sign-up), scans (with LLM fields + patient_id), patients (identifier, name, age, gender, blood_type, medical_notes, total_scans). |
| **AI** | torchxrayvision DenseNet121 | Chest X-ray condition detection (18+ pathologies, confidence ≥ 0.5). |
| **LLM** | Google Gemini | Urgency, reasoning, recommended_action, risk_factors (with optional RAG context). |
| **RAG** | Weaviate (HospitalCases + PatientRecords) | Similar hospital cases (BM25); merged patient history. Seeded once; **every upload adds one case + (if patient) one patient record**. |

**Scan response (all scan endpoints):** 13 fields — scan_id, patient_id, **patient_name**, **patient_age**, **patient_blood_type**, **patient_medical_file**, facility_id, conditions_detected, urgency_ranking, confidence_score, gemini_reasoning, timestamp, image_url.

---

## 1. Current working condition (what works)

### API (Flask)

| Endpoint | Method | Status | Purpose |
|----------|--------|--------|---------|
| `/facilities` | GET | ✅ | List all facilities (id, name, location). Use to map logged-in hospital (e.g. after Google Auth) to `facility_id` for upload/queue. |
| `/facilities` | POST | ✅ | Create a new facility (e.g. when a new hospital signs up). Body: `{"name": "...", "location": "..."}`. Returns new facility (id, name, location). DB then has as many facilities as created. |
| `/upload` | POST | ✅ | Upload X-ray. Form: `file`, **`facility_id`** (any valid id from GET /facilities; default 1), optional `patient_id`, `patient_age`, `patient_gender`, **`patient_name`**, **`patient_blood_type`**, **`patient_medical_notes`** or **`patient_medical_file`**, `use_rag` (default true). Returns full scan object. After save, adds one row to HospitalCases and (if patient_id) one to PatientRecords in Weaviate. |
| `/queue` | GET | ✅ | Prioritized pending scans in same 13-field format; optional `?facility_id=` (any valid facility id). |
| `/scan/<id>` | GET | ✅ | Single scan in same format (includes patient profile when linked). |
| `/scan/<id>/status` | PATCH | ✅ | Update status (e.g. `reviewed`); body `{"status": "reviewed"}`. |
| `/stats` | GET | ✅ | total_scans, avg_urgency, estimated_monthly_cost, scans_by_urgency (critical/urgent/routine). |
| `/health` | GET | ✅ | Liveness + model_loaded. |
| `/admin/seed-weaviate` | POST | ✅ | Seed Weaviate with hospital cases + patient records. |
| `/admin/weaviate-stats` | GET | ✅ | total_hospital_cases, total_patients. |
| `/admin/clear-queue` | POST | ✅ | Delete all scans from SQLite and all files in `uploads/`; returns deleted_scans, deleted_files. |

**Static:** `/static/uploads/<filename>`, `/static/heatmaps/<filename>` serve saved images and heatmaps.

### AI & reasoning

- **Condition detection:** torchxrayvision DenseNet121 (`densenet121-res224-all`) on uploaded image → list of conditions with confidence.
- **Urgency + reasoning:** Gemini (e.g. `gemini-2.0-flash` or `GEMINI_MODEL`) with optional Hybrid RAG:
  - **Hospital RAG:** Up to 3 similar historical cases from Weaviate (BM25 over conditions/outcome/clinical_notes).
  - **Patient RAG:** If `patient_id` provided, **merged** patient history from Weaviate (all PatientRecords for that patient_id: demographics, risk_factors, scan_history combined).
- **Fallback:** If Gemini or RAG fails, rule-based urgency + short reasoning.

### Data stores

- **SQLite (`xray_triage.db`):**
  - **facilities:** Seeded with 3 Montana hospitals (id 1–3). **New facilities** are added via **POST /facilities** (e.g. when a new hospital signs up on the frontend with Google Auth). The DB has **as many facilities as are created** (3 + any created by POST). **There is no login or credentials in the backend**; the frontend uses Google Auth and then sends `facility_id` for the hospital the user belongs to. GET /facilities lists all facilities so the frontend can map “logged-in user’s hospital” to a facility_id; upload and GET /queue use that facility_id.
  - **scans:** id, filename, upload_time, facility_id, urgency_score, conditions (JSON), status, image_path, heatmap_path, reasoning, recommended_action, risk_factors, ai_confidence, patient_id (FK).
  - **patients:** id, patient_identifier (unique), **name**, age, gender, **blood_type**, **medical_notes**, chronic_conditions, first_scan_date, last_scan_date, total_scans. Created/updated when `patient_id` (+ optional name, blood_type, medical_notes) sent on upload.
  - **clear_all_scans()** wipes scans only; facilities and patients kept.
- **Weaviate (localhost:8080):** HospitalCases (historical cases), PatientRecords (patient profiles). Seeded from `seed_medical_data.py`; every upload adds one HospitalCase and (if patient_id) one PatientRecord via **add_scan_to_rag()**. **get_patient_history()** merges all records for a patient_id.

### Demo data (dashboard / presentation)

- **`seed_demo_database.py`:** Populates SQLite with 18 realistic demo scans (no real image files). Run: `python3 seed_demo_database.py`.
  - Mix: 3 critical (9–10), 4 urgent (7–8), 5 moderate (5–6), 6 routine (1–4); spread across all 3 facilities; staggered timestamps (5 min to 6 hours ago).
  - Uses `get_or_create_patient`, `add_scan(..., upload_time=...)`, `update_patient_scan_count`. Safe to run multiple times (adds more rows).
  - After running, GET /queue returns a full, urgency-sorted dashboard for demos.

### Response format (frontend contract)

All scan-bearing responses (POST /upload, GET /queue, GET /scan/<id>) use this shape:

| Field | Type | Description |
|-------|------|-------------|
| `scan_id` | string | Primary key of the scan. |
| `patient_id` | string \| null | Patient identifier (e.g. MRN) if linked. |
| **`patient_name`** | string \| null | Patient display name (from patients.name). |
| **`patient_age`** | int \| null | Patient age (from patients.age). |
| **`patient_blood_type`** | string \| null | e.g. "A+", "O-" (from patients.blood_type). |
| **`patient_medical_file`** | string \| null | Medical notes/file text (from patients.medical_notes). |
| `facility_id` | int | Any valid facility id (from GET /facilities). |
| `conditions_detected` | string[] | Condition names from model. |
| `urgency_ranking` | int | 1–10. |
| `confidence_score` | int | 50, 70, or 90 from ai_confidence. |
| `gemini_reasoning` | string | LLM reasoning text. |
| `timestamp` | string \| null | ISO 8601 upload time. |
| `image_url` | string \| null | e.g. `/static/uploads/<filename>`. |

---

## 2. Tests (what’s passing)

| Test | Command | Pass condition | Notes |
|------|---------|----------------|-------|
| **test_backend.py** | `python3 test_backend.py` | All steps pass | DB init, dummy image, model predict, add_scan, get_queue, get_scan, get_stats. No server. |
| **test_llm_triage.py** | `python3 test_llm_triage.py` (with GEMINI_API_KEY in .env) | 4 cases: urgency + reasoning | Without key: fallback check only. |
| **test_hybrid_rag.py** | `python3 test_hybrid_rag.py` | Weaviate connection, seed, hospital query, patient query, hybrid reasoning, API upload (test 6), upload-updates-RAG (test 7) | Use same Python env as app. Tests 6–7 run when server is up and user presses Enter. |
| **test_api.py** | Server running, then `python3 test_api.py` | All endpoints return 200 | May need updates to assert on new response keys (urgency_ranking, gemini_reasoning, etc.) instead of old ones. |
| **Manual curl** | See TESTING.md or below | Upload / queue / scan return the 9-field format | Verified working. |

---

## 3. Where the data comes from

| What you see | Source |
|--------------|--------|
| **Conditions (e.g. Pneumothorax, Effusion)** | **torchxrayvision** (pre-trained DenseNet121) on the uploaded image. No training in this repo. |
| **all_predictions (per-pathology scores)** | Same model in `xray_model.py`. |
| **urgency_ranking, gemini_reasoning, confidence_score, recommended_action, risk_factors** | **Gemini** in `llm_triage.py`, using: detected conditions, facility name, queue length, and (if RAG) hospital cases + patient record. |
| **Similar hospital cases (e.g. 3)** | **Weaviate** collection **HospitalCases**, seeded from **seed_medical_data.py** (15 curated cases). Queried by BM25 on condition text. |
| **Patient history (e.g. P12345)** | **Weaviate** collection **PatientRecords**, seeded from **seed_medical_data.py** (12 patients). Lookup by exact `patient_id`; merged from all records for that id. |
| **patient_name, patient_age, patient_blood_type, patient_medical_file** | **SQLite** `patients` table (name, age, blood_type, medical_notes). Set/updated on upload via `get_or_create_patient(..., name, blood_type, medical_notes)`; returned via JOIN in get_queue/get_scan. |
| **Facility name, queue length** | **SQLite**: facilities table + count of pending scans. |
| **Stored scans and patients** | **SQLite** via `database.py` (scans + patients tables). |
| **timestamp** | **SQLite** `upload_time` (set on insert), formatted as ISO 8601 in API. |
| **image_url** | Derived from saved file path: `/static/uploads/<filename>`. |

---

## 4. End-to-end pipeline

```
0. (Optional) Client: GET /facilities to list facilities; POST /facilities to create a new hospital. Use facility_id from list or from create response for upload/queue.
1. Client: POST /upload (file, facility_id [must exist in DB], optional patient_id, patient_name, patient_age, patient_gender, patient_blood_type, patient_medical_notes, use_rag=true)
2. App:     Validate file and facility_id (get_facility); save to uploads/ with unique name
3. App:     If patient_id: get_or_create_patient(patient_identifier, age, gender, name, blood_type, medical_notes) in SQLite (create or update profile)
4. Model:   XRayModel.predict_with_hybrid_rag(image_path, facility_name, queue_length, patient_id)
   ├─ 4a. torchxrayvision.predict(image) → conditions + all_predictions
   ├─ 4b. weaviate: find_similar_hospital_cases(condition_names, n=3)
   ├─ 4c. if patient_id: weaviate: get_patient_history(patient_id) [merged from all PatientRecords]
   └─ 4d. Gemini with hybrid prompt (findings + hospital cases + patient history)
           → urgency_score, reasoning, recommended_action, risk_factors, confidence
5. App:     add_scan(..., patient_id=patient_db_id) in SQLite
6. App:     If patient: update_patient_scan_count(patient_db_id)
7. App:     RAG update: get_rag_store().add_scan_to_rag(scan_id, conditions, urgency_score, ...)
            → one new HospitalCases row; if patient_id, one new PatientRecords row (non-blocking; log warning on failure)
8. App:     get_scan(scan_id) → _scan_to_frontend_format(scan) → JSON response (13 fields including patient_name, patient_age, patient_blood_type, patient_medical_file)
9. Client:  Receives full scan object with triage + patient profile fields
```

**Queue flow:** GET /queue → get_queue(facility_id) from SQLite (JOIN patients for name, age, blood_type, medical_notes) → each scan → _scan_to_frontend_format(scan) → { "scans": [ ... ] }.

**Scan detail flow:** GET /scan/<id> → get_scan(id) from SQLite (same JOIN) → _scan_to_frontend_format(scan) → JSON.

---

## 5. Key files

| File | Role |
|------|------|
| `app.py` | Flask app, routes, _scan_to_frontend_format, CORS, init_db; calls add_scan_to_rag after upload. |
| `xray_model.py` | XRayModel: predict(), predict_with_reasoning(), predict_with_hybrid_rag(). |
| `llm_triage.py` | GeminiTriage: assess_urgency(), assess_urgency_hybrid_rag(), _build_hybrid_rag_prompt(). |
| `weaviate_store.py` | HybridRAGStore: HospitalCases + PatientRecords; add_scan_to_rag(), find_similar_hospital_cases(), get_patient_history() (merge), seed_all(), get_stats(). |
| `database.py` | SQLite: init_db, migrations; **get_facilities()**, **get_facility(id)**, **add_facility(name, location)** for dynamic facilities; add_scan, clear_all_scans, get_queue, get_scan, get_stats, get_or_create_patient (with name, blood_type, medical_notes), get_patient_info, update_patient_scan_count. |
| `seed_medical_data.py` | HOSPITAL_CASES (15), PATIENT_RECORDS (12); get_hospital_cases(), get_patient_records(). |
| `seed_demo_database.py` | Seeds 18 demo scans into SQLite for dashboard/presentation. |
| `clear_queue.py` | Standalone script: init_db, clear_all_scans(), delete files in uploads/. |

---

## 6. Environment and run

- **.env:** `GEMINI_API_KEY` (required for Gemini); optional `GEMINI_MODEL` (default gemini-2.0-flash).
- **Weaviate:** Docker via `docker-compose-weaviate.yml` (CLUSTER_HOSTNAME=node1). Seed once: POST /admin/seed-weaviate or `get_rag_store().seed_all()`.
- **Server:** `python3 app.py` (default port 5001).
- **Frontend:** Responses use the 9-field scan format; image_url is under `/static/uploads/`.
- **Demo dashboard:** Run `python3 seed_demo_database.py` once (or more) to fill the queue with 18 realistic scans; then `curl http://127.0.0.1:5001/queue` for a sorted list.
- **Clear queue:** `python clear_queue.py` or `curl -X POST http://127.0.0.1:5001/admin/clear-queue`.

---

## 7. Technical summary: what the system accomplishes

Every technical capability, end to end:

**HTTP & CORS**
- Flask app bound to `0.0.0.0` and configurable port (default 5001) for remote/frontend access.
- CORS: allow-all by default; optional `ALLOWED_ORIGINS` for production.
- Max upload size 10 MB; allowed types jpg, jpeg, png.

**File handling**
- Incoming image saved under `UPLOAD_FOLDER` with a unique name (timestamp + random suffix); heatmaps under `HEATMAP_FOLDER`.
- Static routes serve `/static/uploads/<filename>` and `/static/heatmaps/<filename>`.

**SQLite (xray_triage.db)**
- **facilities:** Seeded with 3 rows (Montana General, Billings Regional, Missoula Community ER). **add_facility(name, location)** adds new facilities (e.g. when a new hospital signs up); **get_facilities()** and **get_facility(id)** for listing/lookup. Upload validates facility_id exists.
- **scans:** id, filename, upload_time, facility_id, urgency_score, conditions (JSON text), status (default pending), image_path, heatmap_path, reasoning, recommended_action, risk_factors, ai_confidence, patient_id (FK to patients). Auto-increment id.
- **patients:** id, patient_identifier (unique), age, gender, **name**, **blood_type**, **medical_notes**, chronic_conditions, first_scan_date, last_scan_date, total_scans. Created on first upload with that patient_id; name/blood_type/medical_notes/age/gender updated when provided on later uploads; total_scans/last_scan_date updated on each upload.
- Migrations: LLM columns, patients table, and patient profile fields (name, blood_type, medical_notes) added idempotently on init.
- **get_queue(facility_id):** Pending scans, JOIN facilities + patients (selects patient_identifier, patient_name, patient_age, patient_blood_type, patient_medical_notes), ordered by urgency_score DESC then upload_time ASC; wait_minutes from julianday diff; conditions/risk_factors parsed from JSON.
- **get_scan(id):** One scan with facility name/location, patient_identifier, and patient_name, patient_age, patient_blood_type, patient_medical_notes from JOIN.
- **get_stats():** total_scans, avg_urgency, estimated_monthly_cost, scans_by_urgency (critical/urgent/routine buckets).
- **clear_all_scans():** DELETE FROM scans; returns count; does not touch facilities or patients.

**Condition detection (xray_model.py)**
- **torchxrayvision** DenseNet121, weights `densenet121-res224-all`; 18+ pathology labels (Pneumothorax, Edema, Effusion, Infiltration, etc.).
- Preprocess: load image, grayscale, resize 224×224, normalize to [-1024, 1024]; output tensor (1, 1, 224, 224).
- Inference: forward pass; scores normalized to [0,1] if logits; conditions with score ≥ 0.5 returned with name, confidence, urgency from URGENCY_MAP (Pneumothorax=10, Edema=8, etc.).
- **predict():** Returns conditions list, max urgency_score, all_predictions dict.
- **predict_with_reasoning():** predict() then Gemini (no RAG) for reasoning/action/risk_factors.
- **predict_with_hybrid_rag():** predict() then Weaviate hospital + patient retrieval, then Gemini with hybrid prompt; returns same shape plus rag_enabled, hospital_cases_used, patient_history_found; fallback on Gemini/RAG failure.

**LLM (llm_triage.py)**
- **Google Gemini** (model from GEMINI_MODEL, e.g. gemini-2.0-flash); API key from GEMINI_API_KEY.
- **assess_urgency():** Single prompt with conditions, facility, queue length, optional patient_context; returns urgency_score, reasoning, recommended_action, risk_factors, confidence.
- **assess_urgency_hybrid_rag():** Same but prompt includes "HOSPITAL PATTERNS" (up to 3 similar cases) and "PATIENT-SPECIFIC CONTEXT" (merged patient record if patient_id); returns same fields plus metadata for RAG.
- Response parsed from JSON in model output; markdown stripped; fallback to rule-based urgency + short message on parse/API error.

**Weaviate (weaviate_store.py)**
- **Connection:** weaviate.connect_to_local(host, port, grpc_port); readiness poll up to 60s to avoid "leader not found."
- **HospitalCases:** case_id, conditions (text array), urgency_score, outcome, time_to_treatment_minutes, facility_type, complications, patient_age_range, final_diagnosis, clinical_notes, content (for BM25). No vectorizer (keyword search).
- **PatientRecords:** patient_id, age, gender, chronic_conditions, risk_factors, scan_history (JSON string), medication_history, last_admission_date, total_previous_scans.
- **add_hospital_case() / add_patient_record():** Insert one object per call (Weaviate client 4.x insert(properties)).
- **add_scan_to_rag():** After each upload: one HospitalCase (case_id=scan-{id}, conditions, urgency, outcome=recommended_action, clinical_notes=reasoning); if patient_id, one PatientRecord (demographics, risk_factors, scan_history=[this scan], total_previous_scans from DB).
- **find_similar_hospital_cases(conditions, n):** BM25 query over content/conditions; returns list of case objects with similarity.
- **get_patient_history(patient_id):** Fetch all PatientRecords with that patient_id (limit 100); merge into one: concatenate scan_history, latest age/gender, max total_previous_scans, union risk_factors.
- **seed_all():** Load seed_medical_data.get_hospital_cases() and get_patient_records(); insert into both collections.
- **get_stats():** Aggregate total count for HospitalCases and PatientRecords.

**API response contract**
- All scan-bearing responses normalized to **13 fields**: scan_id, patient_id, **patient_name**, **patient_age**, **patient_blood_type**, **patient_medical_file**, facility_id, conditions_detected (names only), urgency_ranking (1–10), confidence_score (90/70/50 from ai_confidence), gemini_reasoning, timestamp (ISO 8601), image_url. Patient profile fields are null when no patient is linked or not set.

**Facilities (multi-hospital / Google Auth)**
- **GET /facilities:** List all facilities (id, name, location). Frontend uses this to map logged-in user’s hospital to facility_id.
- **POST /facilities:** Create a new facility (body: name, location). Use when a new hospital signs up; then use returned id for upload and queue.

**Admin & utilities**
- **POST /admin/seed-weaviate:** seed_all(); returns status and get_stats().
- **GET /admin/weaviate-stats:** get_stats().
- **POST /admin/clear-queue:** clear_all_scans() then delete all files in UPLOAD_FOLDER; returns deleted_scans, deleted_files.
- **clear_queue.py:** Same as clear-queue endpoint without server (init_db, clear_all_scans, delete uploads).

**Tests**
- **test_backend.py:** DB init, dummy 224×224 image, model predict, add_scan, get_queue, get_scan, get_stats, update_scan_status.
- **test_llm_triage.py:** Four scenarios (critical/moderate/normal/multiple conditions); requires GEMINI_API_KEY; fallback when quota exceeded.
- **test_hybrid_rag.py:** (1) Weaviate connection, (2) seed, (3) hospital BM25 query, (4) patient history lookup, (5) hybrid RAG reasoning with/without patient_id, (6) full API upload pipeline, (7) upload-updates-RAG (stats before/after upload, patient history retrieval). Tests 6–7 require server + optional Enter.
- **test_api.py:** GET health, POST upload, GET queue, GET scan, GET stats, PATCH status; server must be running.

---

## 8. Summary

- **Works:** Full upload → model → RAG → Gemini → DB → **RAG update (HospitalCases + PatientRecords)** → frontend-format response (13 fields including **patient name, age, blood type, medical file**); queue and scan detail in same format; patient-aware urgency; Weaviate and SQLite both used; admin seed/stats/clear-queue.
- **Dynamic facilities:** GET /facilities lists all; POST /facilities creates a new hospital (e.g. when one signs up via frontend/Google Auth). The DB has as many facilities as created (3 seeded + any new). Upload and queue accept any valid facility_id.
- **Patient profile:** Upload can send patient_name, patient_blood_type, patient_medical_notes; stored in `patients`; returned as patient_name, patient_age, patient_blood_type, patient_medical_file on every scan response when a patient is linked.
- **Tests:** test_backend, test_llm_triage, test_hybrid_rag (including test_7 upload-updates-RAG when server running), test_api when server running.
- **Data:** Conditions from torchxrayvision; urgency/reasoning from Gemini; context from Weaviate (hospital + merged patient history); persistence in SQLite; every upload grows Weaviate for future RAG.
- **Pipeline:** Request → validate → save image → optional patient create/update (with profile fields) → hybrid RAG prediction → save scan → add_scan_to_rag → return formatted JSON.
- **Demo:** `seed_demo_database.py` adds 18 scans with backfilled upload_time; `clear_queue.py` or POST /admin/clear-queue resets queue and uploads.

---

## 9. Quick reference: upload form & scan response

**Facilities (for multi-hospital / Google Auth):**
- **GET /facilities** → `{ "facilities": [ { "id": 1, "name": "Montana General Hospital", "location": "Helena, MT" }, ... ] }`. Use to map logged-in user’s hospital to `facility_id`.
- **POST /facilities** → body `{ "name": "New Hospital", "location": "City, State" }` → `{ "id": 4, "name": "...", "location": "..." }` (201). Call when a new hospital signs up; then use returned `id` as `facility_id` for upload and queue.

**POST /upload** — form/data fields:

| Field | Required | Description |
|-------|----------|-------------|
| `file` | ✅ | Image file (jpg, jpeg, png, max 10 MB). |
| `facility_id` | No (default 1) | Any valid facility id (from GET /facilities). Use POST /facilities to create a new hospital first if needed. |
| `patient_id` | No | Patient identifier (MRN etc.); if set, creates/updates patient and links scan. |
| `patient_age` | No | Integer. |
| `patient_gender` | No | String. |
| `patient_name` | No | Display name; stored in patients.name. |
| `patient_blood_type` | No | e.g. "A+", "O-". |
| `patient_medical_notes` or `patient_medical_file` | No | Medical file/notes text; stored in patients.medical_notes. |
| `use_rag` | No (default true) | "true" or "false". |

**Scan response** (upload, GET /queue, GET /scan/<id>) — JSON shape:

```json
{
  "scan_id": "42",
  "patient_id": "MRN-001",
  "patient_name": "Jane Doe",
  "patient_age": 65,
  "patient_blood_type": "O+",
  "patient_medical_file": "History of COPD; on inhalers.",
  "facility_id": 1,
  "conditions_detected": ["Effusion", "Cardiomegaly"],
  "urgency_ranking": 8,
  "confidence_score": 90,
  "gemini_reasoning": "...",
  "timestamp": "2026-02-06T14:30:00",
  "image_url": "/static/uploads/..."
}
```

Patient profile fields (`patient_name`, `patient_age`, `patient_blood_type`, `patient_medical_file`) are `null` when no patient is linked or not set.
