"""
SQLite database operations for the Rural Hospital AI Radiology Triage System.

Handles facilities, scans, queue ordering, and statistics.
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
DATABASE_PATH = "xray_triage.db"
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Connection helper
# -----------------------------------------------------------------------------


@contextmanager
def get_connection():
    """Context manager for database connections. Ensures commit/rollback and close."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Allow dict-like access by column name
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Schema and seed data
# -----------------------------------------------------------------------------


def init_db() -> None:
    """
    Create facilities and scans tables if they do not exist.
    Seed three Montana rural hospital facilities if the facilities table is empty.
    """
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS facilities (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                facility_id INTEGER,
                urgency_score REAL,
                conditions TEXT,
                status TEXT DEFAULT 'pending',
                image_path TEXT,
                heatmap_path TEXT,
                FOREIGN KEY (facility_id) REFERENCES facilities(id)
            )
        """)

        cur.execute("SELECT COUNT(*) FROM facilities")
        if cur.fetchone()[0] == 0:
            cur.executemany(
                "INSERT INTO facilities (id, name, location) VALUES (?, ?, ?)",
                [
                    (1, "Montana General Hospital", "Helena, MT"),
                    (2, "Billings Regional Medical", "Billings, MT"),
                    (3, "Missoula Community ER", "Missoula, MT"),
                ],
            )
            logger.info("Seeded 3 Montana facilities")

    migrate_add_llm_fields()
    migrate_add_patients_table()
    migrate_add_patient_profile_fields()
    logger.info("Database initialized at %s", DATABASE_PATH)


def get_facilities() -> List[Dict[str, Any]]:
    """Return all facilities (id, name, location). Order by id."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, location FROM facilities ORDER BY id")
        return [dict(row) for row in cur.fetchall()]


def get_facility(facility_id: int) -> Optional[Dict[str, Any]]:
    """Return one facility by id, or None if not found."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, location FROM facilities WHERE id = ?", (facility_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def add_facility(name: str, location: str) -> int:
    """
    Create a new facility (e.g. when a new hospital signs up via your frontend).
    Returns the new facility id.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM facilities")
        new_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO facilities (id, name, location) VALUES (?, ?, ?)",
            (new_id, name.strip(), location.strip()),
        )
        logger.info("Created facility id=%s name=%s", new_id, name)
        return new_id


def migrate_add_patient_profile_fields() -> None:
    """
    Add name, blood_type, medical_notes to patients table for frontend display.
    Safe to run multiple times.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(patients)")
        columns = [row[1] for row in cur.fetchall()]
        for col_name, sql in [
            ("name", "ALTER TABLE patients ADD COLUMN name TEXT"),
            ("blood_type", "ALTER TABLE patients ADD COLUMN blood_type TEXT"),
            ("medical_notes", "ALTER TABLE patients ADD COLUMN medical_notes TEXT"),
        ]:
            if col_name not in columns:
                cur.execute(sql)
                logger.info("Added patients column %s", col_name)
    logger.info("Patient profile fields migration complete")


def migrate_add_patients_table() -> None:
    """
    Add patients table for tracking patient histories.
    Safe to run multiple times.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='patients'"
        )
        if not cur.fetchone():
            cur.execute("""
                CREATE TABLE patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_identifier TEXT UNIQUE NOT NULL,
                    age INTEGER,
                    gender TEXT,
                    chronic_conditions TEXT,
                    first_scan_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_scan_date DATETIME,
                    total_scans INTEGER DEFAULT 0
                )
            """)
            logger.info("Created patients table")
        cur.execute("PRAGMA table_info(scans)")
        columns = [row[1] for row in cur.fetchall()]
        if "patient_id" not in columns:
            cur.execute(
                "ALTER TABLE scans ADD COLUMN patient_id INTEGER REFERENCES patients(id)"
            )
            logger.info("Added patient_id column to scans")
    logger.info("Patient tracking migration complete")


def migrate_add_llm_fields() -> None:
    """
    Add LLM reasoning columns to scans table if they do not exist.
    Safe to run multiple times.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(scans)")
        columns = [row[1] for row in cur.fetchall()]
        for col_name, sql in [
            ("reasoning", "ALTER TABLE scans ADD COLUMN reasoning TEXT"),
            ("recommended_action", "ALTER TABLE scans ADD COLUMN recommended_action TEXT"),
            ("risk_factors", "ALTER TABLE scans ADD COLUMN risk_factors TEXT"),
            ("ai_confidence", "ALTER TABLE scans ADD COLUMN ai_confidence TEXT"),
        ]:
            if col_name not in columns:
                cur.execute(sql)
                logger.info("Added column %s to scans", col_name)
    logger.info("Database migration (LLM fields) complete")


# -----------------------------------------------------------------------------
# Scan operations
# -----------------------------------------------------------------------------


def add_scan(
    filename: str,
    facility_id: int,
    urgency_score: float,
    conditions: List[Dict[str, Any]],
    image_path: str,
    heatmap_path: Optional[str] = None,
    reasoning: Optional[str] = None,
    recommended_action: Optional[str] = None,
    risk_factors: Optional[List[str]] = None,
    ai_confidence: Optional[str] = None,
    patient_id: Optional[int] = None,
    upload_time: Optional[str] = None,
) -> int:
    """
    Insert a new scan record.

    Args:
        filename: Original filename of the upload.
        facility_id: ID of the facility (1, 2, or 3).
        urgency_score: Urgency score from the model (0-10).
        conditions: List of condition dicts; will be stored as JSON.
        image_path: Path to the saved image file.
        heatmap_path: Optional path to heatmap image.
        reasoning: Optional LLM clinical reasoning text.
        recommended_action: Optional immediate/urgent/routine.
        risk_factors: Optional list of risk factors (stored as JSON).
        ai_confidence: Optional high/medium/low.
        patient_id: Optional FK to patients.id.
        upload_time: Optional datetime string (e.g. ISO or 'YYYY-MM-DD HH:MM:SS') for demo/backfill; omit for current time.

    Returns:
        The scan_id of the inserted row.
    """
    conditions_json = json.dumps(conditions)
    risk_factors_json = json.dumps(risk_factors) if risk_factors is not None else None
    with get_connection() as conn:
        cur = conn.cursor()
        if upload_time is not None:
            cur.execute(
                """
                INSERT INTO scans (
                    filename, facility_id, urgency_score, conditions,
                    image_path, heatmap_path, reasoning, recommended_action,
                    risk_factors, ai_confidence, patient_id, upload_time
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    facility_id,
                    urgency_score,
                    conditions_json,
                    image_path,
                    heatmap_path,
                    reasoning,
                    recommended_action,
                    risk_factors_json,
                    ai_confidence,
                    patient_id,
                    upload_time,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO scans (
                    filename, facility_id, urgency_score, conditions,
                    image_path, heatmap_path, reasoning, recommended_action,
                    risk_factors, ai_confidence, patient_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    facility_id,
                    urgency_score,
                    conditions_json,
                    image_path,
                    heatmap_path,
                    reasoning,
                    recommended_action,
                    risk_factors_json,
                    ai_confidence,
                    patient_id,
                ),
            )
        scan_id = cur.lastrowid
    return scan_id


def get_or_create_patient(
    patient_identifier: str,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    name: Optional[str] = None,
    blood_type: Optional[str] = None,
    medical_notes: Optional[str] = None,
) -> int:
    """
    Get existing patient by identifier or create new one.
    When patient exists and name/blood_type/medical_notes are provided, updates those fields.

    Args:
        patient_identifier: Unique patient ID (e.g. medical record number).
        age: Patient age (optional).
        gender: Patient gender (optional).
        name: Patient name (optional).
        blood_type: Blood type e.g. A+, O- (optional).
        medical_notes: Medical file / notes text (optional).

    Returns:
        patients.id (database primary key).
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM patients WHERE patient_identifier = ?",
            (patient_identifier,),
        )
        row = cur.fetchone()
        if row:
            pid = int(row[0])
            # Update profile fields if provided
            updates = []
            params = []
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if blood_type is not None:
                updates.append("blood_type = ?")
                params.append(blood_type)
            if medical_notes is not None:
                updates.append("medical_notes = ?")
                params.append(medical_notes)
            if age is not None:
                updates.append("age = ?")
                params.append(age)
            if gender is not None:
                updates.append("gender = ?")
                params.append(gender)
            if updates:
                params.append(pid)
                cur.execute(
                    "UPDATE patients SET " + ", ".join(updates) + " WHERE id = ?",
                    params,
                )
            return pid
        cur.execute(
            """
            INSERT INTO patients (patient_identifier, age, gender, name, blood_type, medical_notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (patient_identifier, age, gender, name, blood_type, medical_notes),
        )
        return cur.lastrowid


def update_patient_scan_count(patient_id: int) -> None:
    """Increment total_scans and set last_scan_date for a patient."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE patients
            SET total_scans = total_scans + 1,
                last_scan_date = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (patient_id,),
        )


def get_patient_info(patient_id: int) -> Optional[Dict[str, Any]]:
    """
    Get patient information by database ID.

    Returns:
        Patient dict (id, patient_identifier, age, gender, name, blood_type, medical_notes, etc.) or None.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, patient_identifier, age, gender, name, blood_type, medical_notes, first_scan_date, last_scan_date, total_scans FROM patients WHERE id = ?",
            (patient_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return dict(row)


def get_queue(facility_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get prioritized list of pending scans, optionally filtered by facility.

    Joins with facilities for name/location, computes wait time in minutes,
    sorts by urgency_score DESC then upload_time ASC.

    Args:
        facility_id: If provided, only return scans for this facility.

    Returns:
        List of scan dicts with facility_name, wait_minutes, and parsed conditions.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        # Wait time: (now - upload_time) in minutes via julianday
        sql = """
            SELECT
                s.id,
                s.filename,
                s.facility_id,
                f.name AS facility_name,
                s.urgency_score,
                s.conditions,
                s.upload_time,
                s.image_path,
                s.heatmap_path,
                s.reasoning,
                s.recommended_action,
                s.risk_factors,
                s.ai_confidence,
                p.patient_identifier,
                p.name AS patient_name,
                p.age AS patient_age,
                p.blood_type AS patient_blood_type,
                p.medical_notes AS patient_medical_notes,
                ROUND((julianday('now') - julianday(s.upload_time)) * 24 * 60) AS wait_minutes
            FROM scans s
            LEFT JOIN facilities f ON s.facility_id = f.id
            LEFT JOIN patients p ON s.patient_id = p.id
            WHERE s.status = 'pending'
        """
        params: tuple = ()
        if facility_id is not None:
            sql += " AND s.facility_id = ?"
            params = (facility_id,)
        sql += " ORDER BY s.urgency_score DESC, s.upload_time ASC"
        cur.execute(sql, params)
        rows = cur.fetchall()

    result = []
    for row in rows:
        d = dict(row)
        # Parse conditions JSON
        try:
            d["conditions"] = json.loads(d["conditions"]) if d["conditions"] else []
        except (TypeError, json.JSONDecodeError):
            d["conditions"] = []
        # Thumbnail: same as image for now; API can use thumbnail_url = image path
        d["thumbnail_url"] = f"/static/uploads/{Path(d['image_path']).name}" if d.get("image_path") else None
        d["wait_minutes"] = int(d["wait_minutes"]) if d.get("wait_minutes") is not None else 0
        # Parse risk_factors JSON if present
        try:
            d["risk_factors"] = json.loads(d["risk_factors"]) if d.get("risk_factors") else []
        except (TypeError, json.JSONDecodeError):
            d["risk_factors"] = []
        result.append(d)
    return result


def get_scan(scan_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a single scan by ID with facility info and wait time.

    Args:
        scan_id: Primary key of the scan.

    Returns:
        Scan dict with facility_name, facility_location, parsed conditions, wait_minutes,
        image_url, heatmap_url; or None if not found.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                s.id,
                s.filename,
                s.facility_id,
                f.name AS facility_name,
                f.location AS facility_location,
                s.urgency_score,
                s.conditions,
                s.status,
                s.upload_time,
                s.image_path,
                s.heatmap_path,
                s.reasoning,
                s.recommended_action,
                s.risk_factors,
                s.ai_confidence,
                p.patient_identifier,
                p.name AS patient_name,
                p.age AS patient_age,
                p.blood_type AS patient_blood_type,
                p.medical_notes AS patient_medical_notes,
                ROUND((julianday('now') - julianday(s.upload_time)) * 24 * 60) AS wait_minutes
            FROM scans s
            LEFT JOIN facilities f ON s.facility_id = f.id
            LEFT JOIN patients p ON s.patient_id = p.id
            WHERE s.id = ?
            """,
            (scan_id,),
        )
        row = cur.fetchone()

    if row is None:
        return None

    d = dict(row)
    try:
        d["conditions"] = json.loads(d["conditions"]) if d["conditions"] else []
    except (TypeError, json.JSONDecodeError):
        d["conditions"] = []
    d["wait_minutes"] = int(d["wait_minutes"]) if d.get("wait_minutes") is not None else 0
    # Parse risk_factors JSON
    try:
        d["risk_factors"] = json.loads(d["risk_factors"]) if d.get("risk_factors") else []
    except (TypeError, json.JSONDecodeError):
        d["risk_factors"] = []
    # URLs for frontend
    d["image_url"] = f"/static/uploads/{Path(d['image_path']).name}" if d.get("image_path") else None
    d["heatmap_url"] = f"/static/heatmaps/{Path(d['heatmap_path']).name}" if d.get("heatmap_path") else None
    return d


def get_stats() -> Dict[str, Any]:
    """
    Get system statistics for cost comparison and dashboard.

    Returns:
        Dict with total_scans, avg_urgency, estimated_monthly_cost ($0.05 per scan),
        and scans_by_urgency (critical: >=8, urgent: 4-7, routine: <4).
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM scans")
        total_scans = cur.fetchone()[0]
        cur.execute("SELECT AVG(urgency_score) FROM scans")
        row = cur.fetchone()
        avg_urgency = float(row[0]) if row and row[0] is not None else 0.0
        cur.execute(
            """
            SELECT
                SUM(CASE WHEN urgency_score >= 8 THEN 1 ELSE 0 END) AS critical,
                SUM(CASE WHEN urgency_score >= 4 AND urgency_score < 8 THEN 1 ELSE 0 END) AS urgent,
                SUM(CASE WHEN urgency_score < 4 OR urgency_score IS NULL THEN 1 ELSE 0 END) AS routine
            FROM scans
            """
        )
        row = cur.fetchone()
    critical = row[0] or 0
    urgent = row[1] or 0
    routine = row[2] or 0
    # $0.05 per scan -> monthly estimate (assume 30 days; could use actual period)
    cost_per_scan = 0.05
    estimated_monthly_cost = round(total_scans * cost_per_scan, 2)
    return {
        "total_scans": total_scans,
        "avg_urgency": round(avg_urgency, 2),
        "estimated_monthly_cost": estimated_monthly_cost,
        "scans_by_urgency": {
            "critical": critical,
            "urgent": urgent,
            "routine": routine,
        },
    }


def update_scan_status(scan_id: int, status: str) -> bool:
    """
    Update the status of a scan (e.g. when radiologist reviews).

    Args:
        scan_id: Primary key of the scan.
        status: New status (e.g. 'reviewed', 'confirmed').

    Returns:
        True if a row was updated, False otherwise.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE scans SET status = ? WHERE id = ?", (status, scan_id))
        return cur.rowcount > 0


def clear_all_scans() -> int:
    """
    Delete all rows from the scans table. Use for resetting the queue.

    Does not delete patient records (those can stay for RAG/history).
    Does not delete files in uploads/; call clear_upload_files() separately
    or use the /admin/clear-queue endpoint which does both.

    Returns:
        Number of scans deleted.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM scans")
        count = cur.fetchone()[0]
        cur.execute("DELETE FROM scans")
        return count
