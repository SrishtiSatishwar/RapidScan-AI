"""
Hybrid RAG store: Weaviate collections for hospital cases and patient records.

Dual vector/keyword search for hospital patterns and patient history lookup.
"""

import json
import logging
import time
import warnings
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Suppress weaviate deprecation warnings so seed/API output stays clean (Dep005, Dep024, etc.)
warnings.filterwarnings(
    "ignore", category=DeprecationWarning,
    message=".*(weaviate-client|vectorizer_config|vector_config).*"
)

# How long to wait for Weaviate to be ready (leader elected) before giving up
WEAVIATE_READY_TIMEOUT_SEC = 60
WEAVIATE_READY_POLL_INTERVAL_SEC = 2

try:
    import weaviate
    from weaviate.classes.config import Configure, DataType, Property
    from weaviate.classes.query import Filter, MetadataQuery
    # New API uses Configure.Vectors.none(); fallback for older clients
    try:
        _VECTOR_NONE = Configure.Vectors.none()
    except AttributeError:
        _VECTOR_NONE = Configure.Vectorizer.none()
except ImportError as e:
    weaviate = None
    logger.warning("Weaviate client not available: %s", e)
    _VECTOR_NONE = None


def _wait_for_weaviate_ready(client: "weaviate.WeaviateClient") -> None:
    """Poll until Weaviate is ready (leader elected). Avoids 'leader not found' right after container start."""
    deadline = time.monotonic() + WEAVIATE_READY_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            if client.is_ready():
                logger.debug("Weaviate is ready")
                return
        except Exception as e:
            logger.debug("Weaviate not ready yet: %s", e)
        time.sleep(WEAVIATE_READY_POLL_INTERVAL_SEC)
    raise RuntimeError(
        f"Weaviate did not become ready within {WEAVIATE_READY_TIMEOUT_SEC}s. "
        "If you see 'leader not found', run: docker compose -f docker-compose-weaviate.yml down -v && docker compose -f docker-compose-weaviate.yml up -d"
    )


class HybridRAGStore:
    """
    Dual collection system: HospitalCases (historical cases) and PatientRecords (patient profiles).
    """

    def __init__(self, host: str = "localhost", port: int = 8080, grpc_port: int = 50051) -> None:
        """Connect to Weaviate and ensure both collections exist."""
        if weaviate is None:
            raise RuntimeError("weaviate-client is not installed. pip install weaviate-client")
        try:
            self.client = weaviate.connect_to_local(host=host, port=port, grpc_port=grpc_port)
        except Exception as e:
            logger.warning("connect_to_local failed, trying connect_to_custom: %s", e)
            self.client = weaviate.connect_to_custom(
                http_host=host,
                http_port=port,
                http_secure=False,
                grpc_host=host,
                grpc_port=grpc_port,
                grpc_secure=False,
            )
        _wait_for_weaviate_ready(self.client)
        self._create_hospital_cases_collection()
        self._create_patient_records_collection()

    def _create_hospital_cases_collection(self) -> None:
        """Create HospitalCases collection if it does not exist."""
        try:
            if self.client.collections.exists("HospitalCases"):
                logger.info("HospitalCases collection already exists")
                return
        except Exception:
            pass
        try:
            self.client.collections.create(
                name="HospitalCases",
                properties=[
                    Property(name="case_id", data_type=DataType.TEXT),
                    Property(name="conditions", data_type=DataType.TEXT_ARRAY),
                    Property(name="urgency_score", data_type=DataType.NUMBER),
                    Property(name="outcome", data_type=DataType.TEXT),
                    Property(name="time_to_treatment_minutes", data_type=DataType.NUMBER),
                    Property(name="facility_type", data_type=DataType.TEXT),
                    Property(name="complications", data_type=DataType.TEXT_ARRAY),
                    Property(name="patient_age_range", data_type=DataType.TEXT),
                    Property(name="final_diagnosis", data_type=DataType.TEXT),
                    Property(name="clinical_notes", data_type=DataType.TEXT),
                    Property(name="content", data_type=DataType.TEXT),  # for bm25 search
                ],
                vector_config=_VECTOR_NONE,
            )
            logger.info("Created HospitalCases collection")
        except Exception as e:
            logger.warning("Could not create HospitalCases (may already exist): %s", e)

    def _create_patient_records_collection(self) -> None:
        """Create PatientRecords collection if it does not exist."""
        try:
            if self.client.collections.exists("PatientRecords"):
                logger.info("PatientRecords collection already exists")
                return
        except Exception:
            pass
        try:
            self.client.collections.create(
                name="PatientRecords",
                properties=[
                    Property(name="patient_id", data_type=DataType.TEXT),
                    Property(name="age", data_type=DataType.INT),
                    Property(name="gender", data_type=DataType.TEXT),
                    Property(name="chronic_conditions", data_type=DataType.TEXT_ARRAY),
                    Property(name="risk_factors", data_type=DataType.TEXT_ARRAY),
                    Property(name="scan_history", data_type=DataType.TEXT),
                    Property(name="medication_history", data_type=DataType.TEXT_ARRAY),
                    Property(name="last_admission_date", data_type=DataType.TEXT),
                    Property(name="total_previous_scans", data_type=DataType.INT),
                ],
                vector_config=_VECTOR_NONE,
            )
            logger.info("Created PatientRecords collection")
        except Exception as e:
            logger.warning("Could not create PatientRecords (may already exist): %s", e)

    def add_hospital_case(self, case_data: Dict[str, Any]) -> None:
        """Insert one historical case into HospitalCases."""
        conditions = case_data.get("conditions", [])
        content = f"Conditions: {', '.join(conditions)}. Urgency: {case_data.get('urgency_score', 0)}. Outcome: {case_data.get('outcome', '')}. {case_data.get('clinical_notes', '')}"
        properties = {
            "case_id": case_data.get("case_id", ""),
            "conditions": conditions,
            "urgency_score": float(case_data.get("urgency_score", 0)),
            "outcome": case_data.get("outcome", ""),
            "time_to_treatment_minutes": float(case_data.get("time_to_treatment_minutes", 0)),
            "facility_type": case_data.get("facility_type", "rural"),
            "complications": case_data.get("complications", []),
            "patient_age_range": case_data.get("patient_age_range", ""),
            "final_diagnosis": case_data.get("final_diagnosis", ""),
            "clinical_notes": case_data.get("clinical_notes", ""),
            "content": content,
        }
        try:
            collection = self.client.collections.get("HospitalCases")
            collection.data.insert(properties)
            logger.debug("Inserted hospital case %s", case_data.get("case_id"))
        except Exception as e:
            logger.warning("Failed to add hospital case: %s", e)
            raise

    def add_patient_record(self, patient_data: Dict[str, Any]) -> None:
        """Insert one patient profile into PatientRecords. scan_history stored as JSON string."""
        demographics = patient_data.get("demographics", {})
        scan_history = patient_data.get("scan_history", [])
        scan_history_str = json.dumps(scan_history) if scan_history else "[]"
        properties = {
            "patient_id": patient_data.get("patient_id", ""),
            "age": int(demographics.get("age", 0)) if demographics.get("age") is not None else 0,
            "gender": str(demographics.get("gender", "") or ""),
            "chronic_conditions": patient_data.get("chronic_conditions", []),
            "risk_factors": patient_data.get("risk_factors", []),
            "scan_history": scan_history_str,
            "medication_history": patient_data.get("medication_history", []),
            "last_admission_date": str(patient_data.get("last_admission_date") or ""),
            "total_previous_scans": int(patient_data.get("total_previous_scans", 0)),
        }
        try:
            collection = self.client.collections.get("PatientRecords")
            collection.data.insert(properties)
            logger.debug("Inserted patient record %s", patient_data.get("patient_id"))
        except Exception as e:
            logger.warning("Failed to add patient record: %s", e)
            raise

    def add_scan_to_rag(
        self,
        scan_id: int,
        conditions: List[Any],
        urgency_score: float,
        facility_name: str,
        facility_id: int = 1,
        reasoning: Optional[str] = None,
        recommended_action: Optional[str] = None,
        risk_factors: Optional[List[str]] = None,
        patient_identifier: Optional[str] = None,
        patient_age: Optional[int] = None,
        patient_gender: Optional[str] = None,
        total_previous_scans: int = 0,
    ) -> None:
        """
        Add the current scan to both RAG collections so future triage can use it.

        - HospitalCases: one new case (institutional memory).
        - PatientRecords: one new record for this patient (if patient_identifier given).

        conditions: List of condition names (str) or dicts with "name" key (from model).
        """
        # Normalize conditions to list of strings (model returns [{"name": "...", "confidence": ...}])
        conditions_list: List[str] = []
        for c in conditions or []:
            if isinstance(c, str):
                conditions_list.append(c)
            elif isinstance(c, dict) and c.get("name"):
                conditions_list.append(str(c["name"]))
            elif c is not None:
                conditions_list.append(str(c))

        # 1. Add to HospitalCases (every upload grows institutional memory)
        case_id = f"scan-{scan_id}"
        outcome = (recommended_action or "pending review").strip() or "pending review"
        clinical_notes = (reasoning or "").strip()
        final_diagnosis = ", ".join(conditions_list) if conditions_list else "No significant findings"
        content = (
            f"Conditions: {', '.join(conditions_list)}. Urgency: {urgency_score}. "
            f"Outcome: {outcome}. {clinical_notes}"
        )
        patient_age_range = str(patient_age) if patient_age is not None else ""
        self.add_hospital_case({
            "case_id": case_id,
            "conditions": conditions_list,
            "urgency_score": float(urgency_score),
            "outcome": outcome,
            "time_to_treatment_minutes": 0,
            "facility_type": "rural",
            "complications": [],
            "patient_age_range": patient_age_range,
            "final_diagnosis": final_diagnosis,
            "clinical_notes": clinical_notes,
            "content": content,
        })

        # 2. If we have a patient, add to PatientRecords (one record per scan for this patient)
        if patient_identifier:
            scan_entry = {
                "conditions": conditions_list,
                "urgency_score": float(urgency_score),
                "recommended_action": outcome,
            }
            patient_data = {
                "patient_id": patient_identifier,
                "demographics": {"age": patient_age, "gender": patient_gender},
                "chronic_conditions": [],
                "risk_factors": list(risk_factors) if risk_factors else [],
                "scan_history": [scan_entry],
                "medication_history": [],
                "last_admission_date": "",
                "total_previous_scans": int(total_previous_scans),
            }
            self.add_patient_record(patient_data)
            logger.info("Added scan %s to RAG (hospital case + patient %s)", scan_id, patient_identifier)
        else:
            logger.info("Added scan %s to RAG (hospital case only)", scan_id)

    def find_similar_hospital_cases(
        self,
        current_conditions: List[str],
        n_results: int = 3,
    ) -> List[Dict[str, Any]]:
        """Find similar historical cases (keyword search over content + conditions)."""
        if not current_conditions:
            return []
        query_text = " ".join(current_conditions)
        results: List[Dict[str, Any]] = []
        try:
            collection = self.client.collections.get("HospitalCases")
            response = collection.query.bm25(query=query_text, limit=n_results)
            for obj in response.objects:
                props = dict(obj.properties)
                results.append({
                    **props,
                    "similarity": 1.0 - (obj.metadata.score or 0) if hasattr(obj, "metadata") and obj.metadata else 0.8,
                })
            logger.info("Found %d similar hospital cases for %s", len(results), current_conditions)
        except Exception as e:
            logger.warning("Hospital RAG query failed: %s", e)
        return results

    def get_patient_history(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch all patient records for patient_id and merge into one view.
        Each upload adds a new PatientRecords row; we combine scan_histories and use latest demographics.
        """
        try:
            collection = self.client.collections.get("PatientRecords")
            response = collection.query.fetch_objects(
                filters=Filter.by_property("patient_id").equal(patient_id),
                limit=100,
            )
            records = [dict(obj.properties) for obj in response.objects]
            if not records:
                return None
            # Merge: concatenate scan_histories, take latest demographics and max total_previous_scans
            all_scan_histories: List[Dict[str, Any]] = []
            latest_age = 0
            latest_gender = ""
            max_total = 0
            all_risk_factors: List[str] = []
            for props in records:
                sh = props.get("scan_history")
                if sh:
                    try:
                        parsed = json.loads(sh) if isinstance(sh, str) else sh
                        if isinstance(parsed, list):
                            all_scan_histories.extend(parsed)
                    except (TypeError, json.JSONDecodeError):
                        pass
                if props.get("age") is not None:
                    latest_age = int(props["age"])
                if props.get("gender"):
                    latest_gender = str(props["gender"])
                max_total = max(max_total, int(props.get("total_previous_scans", 0)))
                for r in props.get("risk_factors") or []:
                    if r and r not in all_risk_factors:
                        all_risk_factors.append(r)
            merged = {
                "patient_id": patient_id,
                "age": latest_age,
                "gender": latest_gender,
                "chronic_conditions": records[0].get("chronic_conditions", []),
                "risk_factors": all_risk_factors,
                "scan_history": all_scan_histories,
                "medication_history": records[0].get("medication_history", []),
                "last_admission_date": records[0].get("last_admission_date", ""),
                "total_previous_scans": max_total,
            }
            merged["demographics"] = {"age": merged["age"], "gender": merged["gender"]}
            return merged
        except Exception as e:
            logger.warning("Patient history lookup failed for %s: %s", patient_id, e)
        return None

    def seed_hospital_cases(self) -> None:
        """Seed HospitalCases from seed_medical_data."""
        from seed_medical_data import get_hospital_cases
        cases = get_hospital_cases()
        logger.info("Seeding %d hospital cases...", len(cases))
        for case in cases:
            self.add_hospital_case(case)
        logger.info("Seeded %d hospital cases", len(cases))

    def seed_patient_records(self) -> None:
        """Seed PatientRecords from seed_medical_data."""
        from seed_medical_data import get_patient_records
        patients = get_patient_records()
        logger.info("Seeding %d patient records...", len(patients))
        for patient in patients:
            self.add_patient_record(patient)
        logger.info("Seeded %d patient records", len(patients))

    def seed_all(self) -> None:
        """Seed both collections."""
        self.seed_hospital_cases()
        self.seed_patient_records()

    def get_stats(self) -> Dict[str, Any]:
        """Return counts for both collections."""
        total_cases = 0
        total_patients = 0
        try:
            coll_cases = self.client.collections.get("HospitalCases")
            total_cases = coll_cases.aggregate.over_all(total_count=True).total_count
        except Exception as e:
            logger.warning("HospitalCases count failed: %s", e)
        try:
            coll_patients = self.client.collections.get("PatientRecords")
            total_patients = coll_patients.aggregate.over_all(total_count=True).total_count
        except Exception as e:
            logger.warning("PatientRecords count failed: %s", e)
        return {"total_hospital_cases": total_cases, "total_patients": total_patients}

    def close(self) -> None:
        """Close Weaviate connection."""
        try:
            self.client.close()
        except Exception as e:
            logger.warning("Error closing Weaviate client: %s", e)


_rag_store: Optional[HybridRAGStore] = None


def get_rag_store(host: str = "localhost", port: int = 8080, grpc_port: int = 50051) -> HybridRAGStore:
    """Get or create HybridRAGStore singleton."""
    global _rag_store
    if _rag_store is None:
        _rag_store = HybridRAGStore(host=host, port=port, grpc_port=grpc_port)
    return _rag_store
