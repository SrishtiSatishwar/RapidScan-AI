"""
Flask backend for the Rural Hospital AI Radiology Triage System.

Exposes upload, queue, scan detail, stats, and health endpoints.
"""

import os
# Load .env so GEMINI_API_KEY and other vars are available
from dotenv import load_dotenv
load_dotenv()

import logging
import random
import string
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from database import (
    add_facility,
    add_scan,
    clear_all_scans,
    get_facility,
    get_facilities,
    get_or_create_patient,
    get_patient_info,
    get_queue,
    get_scan,
    get_stats,
    init_db,
    update_patient_scan_count,
    update_scan_status,
)
from xray_model import get_model

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
HEATMAP_FOLDER = os.environ.get("HEATMAP_FOLDER", "heatmaps")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(HEATMAP_FOLDER, exist_ok=True)

# CORS: allow frontend (local + remote) and deployment
# For hackathon: allow all origins so teammate can connect from her machine
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "").strip()
if ALLOWED_ORIGINS:
    origins_list = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
    CORS(app, origins=origins_list, supports_credentials=True)
else:
    CORS(app)  # Allow all origins (development / remote teammate / ngrok)

# Ensure DB and migrations run when app is loaded (e.g. test client or gunicorn)
init_db()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in ALLOWED_EXTENSIONS


def unique_filename(original: str) -> str:
    """Generate a unique filename using timestamp and random suffix."""
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else "jpg"
    safe = secure_filename(original) or "image"
    base = safe.rsplit(".", 1)[0] if "." in safe else safe
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{base}_{int(time.time() * 1000)}_{suffix}.{ext}"


def _scan_to_frontend_format(scan: dict, patient_identifier_override: str = None) -> dict:
    """
    Build the frontend-requested scan response shape from a scan dict
    (from get_scan/get_queue or upload result).
    Includes patient profile: name, age, blood_type, medical_file when available.
    """
    conditions_list = scan.get("conditions") or []
    conditions_detected = [
        c.get("name") for c in conditions_list
        if isinstance(c, dict) and c.get("name")
    ]
    urgency_val = float(scan.get("urgency_score") or 0)
    urgency_ranking = max(1, min(10, round(urgency_val)))
    conf = (scan.get("ai_confidence") or "medium").lower()
    confidence_score = 90 if conf == "high" else (70 if conf == "medium" else 50)
    ts = scan.get("upload_time")
    if ts is None:
        timestamp = None
    elif hasattr(ts, "isoformat"):
        timestamp = ts.isoformat()
    else:
        s = str(ts)
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        timestamp = s
    image_path = scan.get("image_path")
    image_url = f"/static/uploads/{Path(image_path).name}" if image_path else None
    patient_id = scan.get("patient_identifier") or patient_identifier_override
    out = {
        "scan_id": str(scan.get("id", "")),
        "patient_id": patient_id if patient_id else None,
        "facility_id": scan.get("facility_id"),
        "conditions_detected": conditions_detected,
        "urgency_ranking": urgency_ranking,
        "confidence_score": confidence_score,
        "gemini_reasoning": scan.get("reasoning") or "",
        "timestamp": timestamp,
        "image_url": image_url,
    }
    # Patient profile for frontend (medical file, name, age, blood type)
    out["patient_name"] = scan.get("patient_name") or None
    out["patient_age"] = scan.get("patient_age") if scan.get("patient_age") is not None else None
    out["patient_blood_type"] = scan.get("patient_blood_type") or None
    out["patient_medical_file"] = scan.get("patient_medical_notes") or None
    return out


# -----------------------------------------------------------------------------
# Static file serving
# -----------------------------------------------------------------------------


@app.route("/static/uploads/<path:filename>")
def serve_upload(filename: str):
    """Serve uploaded X-ray images."""
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/static/heatmaps/<path:filename>")
def serve_heatmap(filename: str):
    """Serve heatmap images."""
    return send_from_directory(HEATMAP_FOLDER, filename)


# -----------------------------------------------------------------------------
# Health check
# -----------------------------------------------------------------------------


@app.route("/health", methods=["GET"])
def health():
    """Health check for deployment and load balancers."""
    try:
        model = get_model()
        model_loaded = model is not None
    except Exception as e:
        logger.warning("Health check: model not loaded: %s", e)
        model_loaded = False
    return jsonify({"status": "healthy", "model_loaded": model_loaded})


# -----------------------------------------------------------------------------
# Facilities (for multi-hospital / Google Auth: list and create facilities)
# -----------------------------------------------------------------------------


@app.route("/facilities", methods=["GET"])
def list_facilities():
    """List all facilities. Frontend can use this to map logged-in hospital to facility_id."""
    try:
        facilities = get_facilities()
        return jsonify({"facilities": facilities}), 200
    except Exception as e:
        logger.exception("List facilities failed")
        return jsonify({"error": str(e)}), 500


@app.route("/facilities", methods=["POST"])
def create_facility():
    """
    Create a new facility (e.g. when a new hospital signs up via your frontend/Google Auth).
    Body: JSON or form with "name" and "location". Returns the new facility (id, name, location).
    """
    try:
        data = request.get_json(silent=True) or request.form
        name = (data.get("name") or "").strip()
        location = (data.get("location") or "").strip()
        if not name:
            return jsonify({"error": "name is required"}), 400
        facility_id = add_facility(name=name, location=location or "Unknown")
        facility = get_facility(facility_id)
        return jsonify(facility), 201
    except Exception as e:
        logger.exception("Create facility failed")
        return jsonify({"error": str(e)}), 500


# -----------------------------------------------------------------------------
# Upload
# -----------------------------------------------------------------------------


@app.route("/upload", methods=["POST"])
def upload():
    """
    Upload endpoint with hybrid RAG support.

    Frontend sends: file (required), facility_id (default 1), and patient info:
    - patient_id (optional; if omitted but name/age/blood_type/medical_notes sent, we create a new patient with a generated id)
    - patient_name, patient_age, patient_blood_type, patient_medical_notes (or patient_medical_file)
    - patient_gender (optional)
    We persist all supplied patient fields to the SQLite patients table and link the scan.
    """
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files["file"]
        if file.filename == "" or not file.filename:
            return jsonify({"error": "No file selected"}), 400
        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type. Use jpg, jpeg, or png"}), 400

        facility_id = request.form.get("facility_id", type=int)
        if facility_id is None:
            facility_id = 1
        facility = get_facility(facility_id)
        if not facility:
            return jsonify({"error": "facility_id not found; use GET /facilities to list valid ids"}), 400

        # Patient data from frontend: name, age, blood_type, medical notes (we add these to SQL DB)
        name = request.form.get("patient_name") or None
        age_raw = request.form.get("patient_age")
        age = int(age_raw) if age_raw not in (None, "") else None
        gender = request.form.get("patient_gender") or None
        blood_type = request.form.get("patient_blood_type") or None
        medical_notes = request.form.get("patient_medical_notes") or request.form.get("patient_medical_file") or None

        patient_identifier = request.form.get("patient_id")
        patient_db_id = None
        # If frontend sent patient_id, use it (create or update that patient with name/age/blood_type/medical_notes)
        if patient_identifier:
            patient_db_id = get_or_create_patient(
                patient_identifier,
                age=age,
                gender=gender,
                name=name,
                blood_type=blood_type,
                medical_notes=medical_notes,
            )
        # If no patient_id but frontend sent any patient info, create a new patient in SQL and link the scan
        elif name or age is not None or blood_type or medical_notes:
            patient_identifier = "PAT-" + str(int(time.time() * 1000))
            patient_db_id = get_or_create_patient(
                patient_identifier,
                age=age,
                gender=gender,
                name=name,
                blood_type=blood_type,
                medical_notes=medical_notes,
            )

        filename = unique_filename(file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)

        facility_name = facility["name"]
        queue_length = len(get_queue(facility_id))

        use_rag = request.form.get("use_rag", "true").lower() == "true"
        model = get_model()

        if use_rag:
            result = model.predict_with_hybrid_rag(
                save_path,
                facility_name=facility_name,
                queue_length=queue_length,
                patient_id=patient_identifier,
            )
        else:
            result = model.predict_with_reasoning(
                save_path,
                facility_name=facility_name,
                queue_length=queue_length,
            )

        urgency_score = result["urgency_score"]
        conditions = result["conditions"]
        heatmap_path = model.get_heatmap(save_path)
        heatmap_save_path = heatmap_path if heatmap_path != save_path else None

        scan_id = add_scan(
            filename=file.filename,
            facility_id=facility_id,
            urgency_score=urgency_score,
            conditions=conditions,
            image_path=save_path,
            heatmap_path=heatmap_save_path,
            reasoning=result.get("reasoning"),
            recommended_action=result.get("recommended_action"),
            risk_factors=result.get("risk_factors"),
            ai_confidence=result.get("confidence"),
            patient_id=patient_db_id,
        )

        if patient_db_id:
            update_patient_scan_count(patient_db_id)

        # Add this scan to both RAG collections so future triage can use it
        try:
            from weaviate_store import get_rag_store
            store = get_rag_store()
            patient_info = get_patient_info(patient_db_id) if patient_db_id else None
            total_previous_scans = (patient_info.get("total_scans") or 0) if patient_info else 0
            store.add_scan_to_rag(
                scan_id=scan_id,
                conditions=conditions,
                urgency_score=urgency_score,
                facility_name=facility_name,
                facility_id=facility_id,
                reasoning=result.get("reasoning"),
                recommended_action=result.get("recommended_action"),
                risk_factors=result.get("risk_factors"),
                patient_identifier=patient_identifier,
                patient_age=patient_info.get("age") if patient_info else request.form.get("patient_age", type=int) or None,
                patient_gender=(patient_info.get("gender") or request.form.get("patient_gender")) if patient_info else request.form.get("patient_gender"),
                total_previous_scans=total_previous_scans,
            )
        except Exception as e:
            logger.warning("RAG update failed (upload succeeded): %s", e)

        scan_row = get_scan(scan_id)
        if scan_row:
            response_data = _scan_to_frontend_format(scan_row, patient_identifier_override=patient_identifier)
        else:
            patient_info = get_patient_info(patient_db_id) if patient_db_id else None
            response_data = _scan_to_frontend_format(
                {
                    "id": scan_id,
                    "patient_identifier": patient_identifier,
                    "facility_id": facility_id,
                    "conditions": conditions,
                    "urgency_score": urgency_score,
                    "ai_confidence": result.get("confidence"),
                    "reasoning": result.get("reasoning"),
                    "upload_time": None,
                    "image_path": save_path,
                    "patient_name": patient_info.get("name") if patient_info else request.form.get("patient_name"),
                    "patient_age": patient_info.get("age") if patient_info else request.form.get("patient_age", type=int),
                    "patient_blood_type": patient_info.get("blood_type") if patient_info else request.form.get("patient_blood_type"),
                    "patient_medical_notes": patient_info.get("medical_notes") if patient_info else request.form.get("patient_medical_notes") or request.form.get("patient_medical_file"),
                },
                patient_identifier_override=patient_identifier,
            )
        return jsonify(response_data), 200
    except (FileNotFoundError, ValueError) as e:
        logger.warning("Upload validation error: %s", e)
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        logger.exception("Upload inference error")
        return jsonify({"error": "Analysis failed"}), 500
    except Exception as e:
        logger.exception("Upload failed")
        return jsonify({"error": "Upload failed"}), 500


# -----------------------------------------------------------------------------
# Queue
# -----------------------------------------------------------------------------


@app.route("/queue", methods=["GET"])
def queue():
    """Return prioritized list of pending scans in frontend format."""
    try:
        facility_id = request.args.get("facility_id", type=int)
        scans = get_queue(facility_id=facility_id)
        out = [_scan_to_frontend_format(s) for s in scans]
        return jsonify({"scans": out})
    except Exception as e:
        logger.exception("Queue failed")
        return jsonify({"error": "Failed to fetch queue"}), 500


# -----------------------------------------------------------------------------
# Scan detail
# -----------------------------------------------------------------------------


@app.route("/scan/<int:scan_id>", methods=["GET"])
def scan_detail(scan_id: int):
    """Return single scan in frontend format."""
    try:
        scan = get_scan(scan_id)
        if scan is None:
            return jsonify({"error": "Scan not found"}), 404
        return jsonify(_scan_to_frontend_format(scan))
    except Exception as e:
        logger.exception("Scan detail failed")
        return jsonify({"error": "Failed to fetch scan"}), 500


# -----------------------------------------------------------------------------
# Update scan status
# -----------------------------------------------------------------------------


@app.route("/scan/<int:scan_id>/status", methods=["PATCH"])
def scan_status(scan_id: int):
    """Update scan status (e.g. when radiologist reviews)."""
    try:
        data = request.get_json(silent=True) or {}
        status = data.get("status")
        if not status or not isinstance(status, str):
            return jsonify({"error": "Missing or invalid 'status' in body"}), 400
        updated = update_scan_status(scan_id, status.strip())
        if not updated:
            return jsonify({"error": "Scan not found"}), 404
        return jsonify({"success": True})
    except Exception as e:
        logger.exception("Update status failed")
        return jsonify({"error": "Failed to update status"}), 500


# -----------------------------------------------------------------------------
# Stats
# -----------------------------------------------------------------------------


@app.route("/stats", methods=["GET"])
def stats():
    """Return system statistics for cost comparison."""
    try:
        return jsonify(get_stats())
    except Exception as e:
        logger.exception("Stats failed")
        return jsonify({"error": "Failed to fetch stats"}), 500


# -----------------------------------------------------------------------------
# Admin: Weaviate seed and stats
# -----------------------------------------------------------------------------


@app.route("/admin/seed-weaviate", methods=["POST"])
def seed_weaviate():
    """Seed both hospital cases and patient records in Weaviate."""
    try:
        from weaviate_store import get_rag_store

        store = get_rag_store()
        store.seed_all()
        stats = store.get_stats()
        return jsonify({
            "status": "success",
            "message": "Weaviate seeded with hospital cases and patient records",
            "stats": stats,
        }), 200
    except Exception as e:
        logger.exception("Seed Weaviate failed")
        return jsonify({"error": str(e)}), 500


@app.route("/admin/weaviate-stats", methods=["GET"])
def weaviate_stats():
    """Get Weaviate database statistics."""
    try:
        from weaviate_store import get_rag_store

        store = get_rag_store()
        return jsonify(store.get_stats()), 200
    except Exception as e:
        logger.warning("Weaviate stats failed: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/admin/clear-queue", methods=["POST"])
def clear_queue():
    """Remove all scans from the queue and delete uploaded image files. Start afresh."""
    try:
        deleted = clear_all_scans()
        # Remove files in uploads folder so disk is clean
        upload_dir = Path(UPLOAD_FOLDER)
        removed_files = 0
        if upload_dir.exists():
            for f in upload_dir.iterdir():
                if f.is_file():
                    try:
                        f.unlink()
                        removed_files += 1
                    except OSError as e:
                        logger.warning("Could not delete %s: %s", f, e)
        return jsonify({
            "status": "success",
            "deleted_scans": deleted,
            "deleted_files": removed_files,
            "message": f"Queue cleared: {deleted} scans removed, {removed_files} files deleted.",
        }), 200
    except Exception as e:
        logger.exception("Clear queue failed")
        return jsonify({"error": str(e)}), 500


# -----------------------------------------------------------------------------
# Startup
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    init_db()
    # Load model at startup so first request is fast
    try:
        get_model()
        logger.info("Model loaded at startup")
    except Exception as e:
        logger.warning("Model not loaded at startup: %s", e)
    # host='0.0.0.0' allows connections from any IP (teammate on same WiFi, ngrok, Render)
    # port = int(os.environ.get("PORT", 5001))
    # debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    # app.run(host="0.0.0.0", port=port, debug=debug)
    import os
    
    # Read from environment or use defaults
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print("=" * 60)
    print(f"🚀 VitalTriage Backend Starting")
    print(f"📍 Server: http://{host}:{port}")
    print(f"🔧 Debug Mode: {debug}")
    print(f"🔑 Gemini API Key: {'✓ Set' if os.getenv('GEMINI_API_KEY') else '✗ MISSING'}")
    print("=" * 60)
    
    app.run(host=host, port=port, debug=debug)

