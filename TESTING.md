# Backend testing guide

## Quick pipeline check (run in this order)

From the **backend** directory:

```bash
# 1. Dependencies
pip install -r requirements.txt

# 2. Backend test (DB + model + DB functions) — no server
python3 test_backend.py

# 3. Optional: LLM test (use if GEMINI_API_KEY is in .env)
python3 test_llm_triage.py
```

Then in **two separate terminals**:

**Terminal A (leave running):**
```bash
cd backend
python3 app.py
```

**Terminal B:**
```bash
cd backend
python3 test_api.py
```

If all four steps succeed (backend test, optional LLM test, server starts, API test passes), the whole pipeline is good.

---

## Full integrated pipeline test (X-ray model + Gemini + API)

This runs the **entire** flow: real image → torchxrayvision → conditions → Gemini reasoning → DB → API response.

**1. Ensure `.env` has your Gemini key** (so the server uses Gemini, not fallback):

```bash
# backend/.env should contain:
GEMINI_API_KEY=your_actual_key
# optional if you changed model:
# GEMINI_MODEL=gemini-2.0-flash
```

**2. Start the server** (it loads `.env` on startup):

```bash
cd backend
python3 app.py
```

Leave this running. You should see “Model loaded at startup” and “Running on http://0.0.0.0:5001”.

**3. In a second terminal, run the API test** (it uploads a test image and hits all endpoints):

```bash
cd backend
python3 test_api.py
```

**What this does:**  
- POST /upload sends `test_images/normal/dummy_test_224.png` to the server.  
- The server runs **predict_with_reasoning()**: torchxrayvision on the image → conditions → Gemini **assess_urgency(conditions, …)** → urgency + reasoning + recommended_action.  
- The response and later GET /scan/<id> include that reasoning.  
- So you’re testing: **image → X-ray model → LLM → DB → API**.

**Success:** You see “ALL API TESTS PASSED” and in the output, the upload and scan-detail steps show **reasoning** and **recommended_action** from Gemini (not “Fallback: no LLM available”).

**Quick one-liner check (after server is running):**

```bash
# From backend dir, with server already running:
python3 -c "
import requests
with open('test_images/normal/dummy_test_224.png','rb') as f:
    r = requests.post('http://127.0.0.1:5001/upload', files={'file':('x.png',f)}, data={'facility_id':'1'}, timeout=30)
d = r.json()
print('Urgency:', d.get('urgency_score'))
print('Reasoning:', (d.get('reasoning') or '')[:150])
print('Action:', d.get('recommended_action'))
print('OK' if d.get('reasoning') and 'Fallback' not in (d.get('reasoning') or '') else 'Check: Gemini may not be used')
"
```

If the printed reasoning is a full clinical sentence (not “Fallback: no LLM available”), the full pipeline is working.

---

## 1. Install dependencies (including requests)

```bash
cd backend
pip install -r requirements.txt
```

## 2. Run the backend test (no server needed)

This tests the database, a dummy image, model inference, and all DB functions.

```bash
python3 test_backend.py
```

**Expected output:** All steps show `[PASS]`, then:

```
============================================================
ALL BACKEND TESTS PASSED
============================================================
```

Example full output:

```
============================================================
BACKEND TEST: database, image, model, DB functions
============================================================

1. Database initialization
  [PASS] init_db()

2. Create dummy test image (224x224 grayscale)
  [PASS] Create and save dummy image to test_images/normal/
      Saved to: test_images/normal/dummy_test_224.png

3. Model inference on dummy image
  [PASS] get_model()
  [PASS] model.predict(dummy_image)
      urgency_score=..., conditions=...

4. Database functions
  [PASS] add_scan(...)
  [PASS] get_queue()
  [PASS] get_queue(facility_id=1)
  [PASS] get_scan(scan_id)
  [PASS] get_stats()
  [PASS] update_scan_status(scan_id, 'reviewed')

============================================================
ALL BACKEND TESTS PASSED
============================================================
```

The script also creates `test_images/normal/dummy_test_224.png` if it doesn’t exist.

---

## 3. Start the Flask server

In a **separate terminal**, from the backend directory:

```bash
cd backend
python3 app.py
```

You should see something like:

```
INFO:database:Database initialized at xray_triage.db
INFO:xray_model:XRayModel loaded successfully with 18 pathologies
INFO:__main__:Model loaded at startup
 * Serving Flask app 'app'
 * Running on http://0.0.0.0:5001
```

Leave this terminal running.

---

## 4. Run the API test (server must be running)

In **another terminal**:

```bash
cd backend
python3 test_api.py
```

**Expected output:** Each endpoint prints its response, then `[OK]`, and at the end:

```
============================================================
ALL API TESTS PASSED
============================================================
```

Example (abbreviated):

```
============================================================
API TEST
BASE_URL = http://localhost:5001
============================================================

Test image: test_images/normal/dummy_test_224.png

--- GET /health ---
Status: 200
Response: {'model_loaded': True, 'status': 'healthy'}
  [OK]

--- POST /upload ---
Status: 200
Response: {'message': 'Scan uploaded and analyzed', 'scan_id': 5, 'status': 'success', 'urgency_score': 7.0}
  [OK]

--- GET /queue ---
...
--- GET /scan/5 ---
...
--- GET /stats ---
...
--- PATCH /scan/5/status ---
...

============================================================
ALL API TESTS PASSED
============================================================
```

If the server is **not** running, you’ll see:

```
[FAIL] Could not connect to http://localhost:5001. Is the Flask server running?
  Start it with: python3 app.py
```

To use a different base URL (e.g. port 5000 or a deployed URL):

```bash
BASE_URL=http://localhost:5000 python3 test_api.py
```

---

## 5. LLM triage test (optional)

With Gemini integration, you can test the LLM reasoning path:

```bash
export GEMINI_API_KEY=your_key   # from https://aistudio.google.com/app/apikey
python3 test_llm_triage.py
```

Without `GEMINI_API_KEY`, the script runs a quick fallback check and skips live Gemini calls. Upload and scan detail still work using rule-based fallback urgency.

---

## Summary of commands

| Step | Command |
|------|--------|
| Install deps | `pip install -r requirements.txt` |
| Backend test (no server) | `python3 test_backend.py` |
| Start server | `python3 app.py` (in one terminal) |
| API test (server running) | `python3 test_api.py` (in another terminal) |
| LLM test (optional) | `GEMINI_API_KEY=... python3 test_llm_triage.py` |
