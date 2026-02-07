"""
Seed data for Hybrid RAG: hospital cases and patient records.

Used by weaviate_store to populate HospitalCases and PatientRecords collections.
"""

from typing import Any, Dict, List

# -----------------------------------------------------------------------------
# HOSPITAL_CASES: Historical cases from Montana General Hospital (15-20 cases)
# -----------------------------------------------------------------------------

HOSPITAL_CASES: List[Dict[str, Any]] = [
    # Pneumothorax (3: severe, moderate, mild)
    {
        "case_id": "PTX001",
        "conditions": ["Pneumothorax"],
        "confidence_scores": {"Pneumothorax": 0.95},
        "urgency_score": 10,
        "outcome": "Emergency chest tube placement within 15 minutes. Patient stabilized.",
        "time_to_treatment_minutes": 15,
        "facility_type": "rural",
        "complications": ["Respiratory_distress"],
        "patient_age_range": "60-70",
        "final_diagnosis": "Large spontaneous pneumothorax",
        "clinical_notes": "Rapid deterioration prevented by immediate intervention",
    },
    {
        "case_id": "PTX002",
        "conditions": ["Pneumothorax"],
        "confidence_scores": {"Pneumothorax": 0.78},
        "urgency_score": 8,
        "outcome": "Moderate pneumothorax. Observation then chest tube at 45 min.",
        "time_to_treatment_minutes": 45,
        "facility_type": "rural",
        "complications": [],
        "patient_age_range": "40-50",
        "final_diagnosis": "Moderate spontaneous pneumothorax",
        "clinical_notes": "Stable on presentation, intervention when oxygen requirement increased",
    },
    {
        "case_id": "PTX003",
        "conditions": ["Pneumothorax"],
        "confidence_scores": {"Pneumothorax": 0.55},
        "urgency_score": 6,
        "outcome": "Small apical pneumothorax. Discharged with follow-up. Resolved spontaneously.",
        "time_to_treatment_minutes": 0,
        "facility_type": "rural",
        "complications": [],
        "patient_age_range": "20-30",
        "final_diagnosis": "Small spontaneous pneumothorax",
        "clinical_notes": "Young healthy patient, minimal symptoms",
    },
    # Pleural Effusion (3 cases)
    {
        "case_id": "EFF001",
        "conditions": ["Effusion"],
        "confidence_scores": {"Effusion": 0.92},
        "urgency_score": 8,
        "outcome": "Large pleural effusion. Thoracentesis performed. 800ml drained.",
        "time_to_treatment_minutes": 60,
        "facility_type": "rural",
        "complications": ["Dyspnea"],
        "patient_age_range": "70-80",
        "final_diagnosis": "Large unilateral pleural effusion, likely malignant",
        "clinical_notes": "Significant symptomatic relief after drainage",
    },
    {
        "case_id": "EFF002",
        "conditions": ["Effusion"],
        "confidence_scores": {"Effusion": 0.75},
        "urgency_score": 6,
        "outcome": "Moderate effusion. Diuretics started. Admitted for CHF exacerbation.",
        "time_to_treatment_minutes": 120,
        "facility_type": "rural",
        "complications": [],
        "patient_age_range": "65-75",
        "final_diagnosis": "Pleural effusion secondary to heart failure",
        "clinical_notes": "Known CHF, responded to diuresis",
    },
    {
        "case_id": "EFF003",
        "conditions": ["Effusion"],
        "confidence_scores": {"Effusion": 0.58},
        "urgency_score": 4,
        "outcome": "Small effusion. Outpatient follow-up. Resolved on repeat imaging.",
        "time_to_treatment_minutes": 0,
        "facility_type": "rural",
        "complications": [],
        "patient_age_range": "50-60",
        "final_diagnosis": "Small benign pleural effusion",
        "clinical_notes": "Incidental finding, asymptomatic",
    },
    # Pneumonia/Infiltration (3 cases)
    {
        "case_id": "PNA001",
        "conditions": ["Pneumonia", "Infiltration"],
        "confidence_scores": {"Pneumonia": 0.88, "Infiltration": 0.82},
        "urgency_score": 8,
        "outcome": "Severe pneumonia. ICU admission. Intubated within 4 hours.",
        "time_to_treatment_minutes": 90,
        "facility_type": "rural",
        "complications": ["Respiratory_failure", "Sepsis"],
        "patient_age_range": "75-85",
        "final_diagnosis": "Severe community-acquired pneumonia",
        "clinical_notes": "Rapid progression, required transfer to tertiary center",
    },
    {
        "case_id": "PNA002",
        "conditions": ["Infiltration"],
        "confidence_scores": {"Infiltration": 0.72},
        "urgency_score": 6,
        "outcome": "Lobar pneumonia. Admitted for IV antibiotics. Discharged day 5.",
        "time_to_treatment_minutes": 180,
        "facility_type": "rural",
        "complications": [],
        "patient_age_range": "55-65",
        "final_diagnosis": "Right lower lobe pneumonia",
        "clinical_notes": "Stable on admission, good response to therapy",
    },
    {
        "case_id": "PNA003",
        "conditions": ["Infiltration"],
        "confidence_scores": {"Infiltration": 0.55},
        "urgency_score": 4,
        "outcome": "Mild infiltrate. Oral antibiotics. Outpatient follow-up.",
        "time_to_treatment_minutes": 0,
        "facility_type": "rural",
        "complications": [],
        "patient_age_range": "30-40",
        "final_diagnosis": "Mild bronchopneumonia",
        "clinical_notes": "Ambulatory, low risk",
    },
    # Cardiomegaly + Edema (2 cases)
    {
        "case_id": "CAR001",
        "conditions": ["Cardiomegaly", "Edema"],
        "confidence_scores": {"Cardiomegaly": 0.90, "Edema": 0.85},
        "urgency_score": 9,
        "outcome": "Acute decompensated heart failure. ICU admission. Diuresis and vasodilators.",
        "time_to_treatment_minutes": 25,
        "facility_type": "rural",
        "complications": ["Respiratory_distress", "Hypotension"],
        "patient_age_range": "70-80",
        "final_diagnosis": "Acute on chronic systolic heart failure",
        "clinical_notes": "Critical presentation, required urgent intervention",
    },
    {
        "case_id": "CAR002",
        "conditions": ["Cardiomegaly"],
        "confidence_scores": {"Cardiomegaly": 0.78},
        "urgency_score": 5,
        "outcome": "Stable cardiomegaly. Cardiology referral. Outpatient echo scheduled.",
        "time_to_treatment_minutes": 0,
        "facility_type": "rural",
        "complications": [],
        "patient_age_range": "60-70",
        "final_diagnosis": "Chronic cardiomegaly, likely hypertensive",
        "clinical_notes": "Known hypertension, stable",
    },
    # Mass/Nodule (2 cases)
    {
        "case_id": "MAS001",
        "conditions": ["Mass"],
        "confidence_scores": {"Mass": 0.85},
        "urgency_score": 6,
        "outcome": "Lung mass. CT ordered. Biopsy later confirmed malignancy.",
        "time_to_treatment_minutes": 1440,
        "facility_type": "rural",
        "complications": [],
        "patient_age_range": "65-75",
        "final_diagnosis": "Primary lung adenocarcinoma",
        "clinical_notes": "Referred to oncology",
    },
    {
        "case_id": "NOD001",
        "conditions": ["Nodule"],
        "confidence_scores": {"Nodule": 0.70},
        "urgency_score": 4,
        "outcome": "Indeterminate nodule. 3-month follow-up CT recommended.",
        "time_to_treatment_minutes": 0,
        "facility_type": "rural",
        "complications": [],
        "patient_age_range": "50-60",
        "final_diagnosis": "Indeterminate pulmonary nodule",
        "clinical_notes": "Low-risk patient, routine surveillance",
    },
    # Normal/minor (2 cases)
    {
        "case_id": "NOR001",
        "conditions": [],
        "confidence_scores": {},
        "urgency_score": 1,
        "outcome": "Normal chest X-ray. Discharged. No intervention.",
        "time_to_treatment_minutes": 0,
        "facility_type": "rural",
        "complications": [],
        "patient_age_range": "25-35",
        "final_diagnosis": "Normal",
        "clinical_notes": "Routine pre-employment screening",
    },
    {
        "case_id": "NOR002",
        "conditions": ["Atelectasis"],
        "confidence_scores": {"Atelectasis": 0.52},
        "urgency_score": 2,
        "outcome": "Minor atelectasis. Incentive spirometry. Discharged same day.",
        "time_to_treatment_minutes": 0,
        "facility_type": "rural",
        "complications": [],
        "patient_age_range": "40-50",
        "final_diagnosis": "Subsegmental atelectasis",
        "clinical_notes": "Post-operative, expected finding",
    },
]

# -----------------------------------------------------------------------------
# PATIENT_RECORDS: Patient profiles for patient-level RAG (10-12 patients)
# -----------------------------------------------------------------------------

PATIENT_RECORDS: List[Dict[str, Any]] = [
    # High-risk (3-4): elderly, COPD, CHF, diabetes
    {
        "patient_id": "P12345",
        "demographics": {"age": 72, "gender": "M"},
        "chronic_conditions": ["COPD", "Hypertension", "Diabetes"],
        "risk_factors": ["Smoker_40_years", "COPD_severe", "Previous_ICU_admission"],
        "scan_history": [
            {
                "date": "2025-06-15",
                "scan_id": "PTX001",
                "findings": ["Pneumothorax"],
                "urgency": 10,
                "outcome": "Required ICU admission, chest tube placement",
                "complications": ["Respiratory_failure"],
                "treatment_duration_days": 5,
            },
            {
                "date": "2025-01-10",
                "findings": ["Emphysema"],
                "urgency": 4,
                "outcome": "Stable, outpatient management",
            },
        ],
        "medication_history": ["Albuterol", "Metformin", "Lisinopril"],
        "last_admission_date": "2025-06-15",
        "total_previous_scans": 3,
    },
    {
        "patient_id": "P12346",
        "demographics": {"age": 78, "gender": "F"},
        "chronic_conditions": ["CHF", "Atrial_fibrillation", "CKD"],
        "risk_factors": ["Previous_ICU_admission", "Multiple_admissions"],
        "scan_history": [
            {
                "date": "2025-05-20",
                "scan_id": "CAR001",
                "findings": ["Cardiomegaly", "Edema"],
                "urgency": 9,
                "outcome": "Acute heart failure, ICU admission",
                "complications": ["Respiratory_distress"],
                "treatment_duration_days": 7,
            },
        ],
        "medication_history": ["Furosemide", "Metoprolol", "Apixaban"],
        "last_admission_date": "2025-05-20",
        "total_previous_scans": 2,
    },
    {
        "patient_id": "P12347",
        "demographics": {"age": 65, "gender": "M"},
        "chronic_conditions": ["COPD", "Diabetes"],
        "risk_factors": ["Smoker_30_years", "Diabetic_complications"],
        "scan_history": [
            {
                "date": "2025-04-01",
                "findings": ["Pneumonia", "Infiltration"],
                "urgency": 7,
                "outcome": "Admitted for pneumonia, required oxygen",
                "complications": [],
                "treatment_duration_days": 4,
            },
        ],
        "medication_history": ["Insulin", "Prednisone", "Albuterol"],
        "last_admission_date": "2025-04-01",
        "total_previous_scans": 2,
    },
    {
        "patient_id": "P12348",
        "demographics": {"age": 70, "gender": "F"},
        "chronic_conditions": ["Hypertension", "Diabetes", "Obesity"],
        "risk_factors": ["BMI_38", "Previous_effusion"],
        "scan_history": [
            {
                "date": "2025-03-10",
                "scan_id": "EFF001",
                "findings": ["Effusion"],
                "urgency": 8,
                "outcome": "Thoracentesis, large volume drained",
                "complications": [],
                "treatment_duration_days": 2,
            },
        ],
        "medication_history": ["Lisinopril", "Metformin", "Omeprazole"],
        "last_admission_date": "2025-03-10",
        "total_previous_scans": 1,
    },
    # Medium-risk (3-4)
    {
        "patient_id": "P12349",
        "demographics": {"age": 55, "gender": "M"},
        "chronic_conditions": ["Hypertension"],
        "risk_factors": ["Previous_mild_findings"],
        "scan_history": [
            {
                "date": "2025-02-15",
                "findings": ["Infiltration"],
                "urgency": 5,
                "outcome": "Outpatient antibiotics, resolved",
            },
        ],
        "medication_history": ["Lisinopril"],
        "last_admission_date": None,
        "total_previous_scans": 1,
    },
    {
        "patient_id": "P12350",
        "demographics": {"age": 58, "gender": "F"},
        "chronic_conditions": ["Asthma"],
        "risk_factors": [],
        "scan_history": [
            {
                "date": "2024-11-01",
                "findings": ["Atelectasis"],
                "urgency": 3,
                "outcome": "Resolved with bronchodilators",
            },
        ],
        "medication_history": ["Inhaled corticosteroid"],
        "last_admission_date": None,
        "total_previous_scans": 1,
    },
    {
        "patient_id": "P12351",
        "demographics": {"age": 52, "gender": "M"},
        "chronic_conditions": ["GERD"],
        "risk_factors": [],
        "scan_history": [
            {
                "date": "2025-01-20",
                "findings": ["Cardiomegaly"],
                "urgency": 4,
                "outcome": "Outpatient cardiology referral",
            },
        ],
        "medication_history": ["Omeprazole"],
        "last_admission_date": None,
        "total_previous_scans": 1,
    },
    {
        "patient_id": "P12352",
        "demographics": {"age": 60, "gender": "F"},
        "chronic_conditions": ["Hypothyroidism"],
        "risk_factors": [],
        "scan_history": [
            {
                "date": "2024-09-10",
                "findings": ["Nodule"],
                "urgency": 4,
                "outcome": "Follow-up CT in 6 months, stable",
            },
        ],
        "medication_history": ["Levothyroxine"],
        "last_admission_date": None,
        "total_previous_scans": 1,
    },
    # Low-risk (3-4)
    {
        "patient_id": "P67890",
        "demographics": {"age": 28, "gender": "M"},
        "chronic_conditions": [],
        "risk_factors": [],
        "scan_history": [
            {
                "date": "2025-07-01",
                "findings": ["Pneumothorax"],
                "urgency": 8,
                "outcome": "Small pneumothorax, observation, resolved",
                "complications": [],
                "treatment_duration_days": 1,
            },
        ],
        "medication_history": [],
        "last_admission_date": "2025-07-01",
        "total_previous_scans": 1,
    },
    {
        "patient_id": "P67891",
        "demographics": {"age": 35, "gender": "F"},
        "chronic_conditions": [],
        "risk_factors": [],
        "scan_history": [],
        "medication_history": [],
        "last_admission_date": None,
        "total_previous_scans": 0,
    },
    {
        "patient_id": "P67892",
        "demographics": {"age": 42, "gender": "M"},
        "chronic_conditions": [],
        "risk_factors": [],
        "scan_history": [
            {
                "date": "2024-12-01",
                "findings": [],
                "urgency": 1,
                "outcome": "Normal, pre-op clearance",
            },
        ],
        "medication_history": [],
        "last_admission_date": None,
        "total_previous_scans": 1,
    },
    {
        "patient_id": "P67893",
        "demographics": {"age": 25, "gender": "F"},
        "chronic_conditions": [],
        "risk_factors": [],
        "scan_history": [],
        "medication_history": [],
        "last_admission_date": None,
        "total_previous_scans": 0,
    },
]


def get_hospital_cases() -> List[Dict[str, Any]]:
    """Return list of historical hospital cases for seeding Weaviate."""
    return HOSPITAL_CASES


def get_patient_records() -> List[Dict[str, Any]]:
    """Return list of patient profiles for seeding Weaviate."""
    return PATIENT_RECORDS
