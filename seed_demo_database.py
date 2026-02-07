"""
Seed the SQLite database with realistic demo scan data for dashboard presentation.

Run: python3 seed_demo_database.py

Safe to run multiple times (adds new rows; patient get_or_create avoids duplicates by identifier).
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from database import (
    add_scan,
    get_or_create_patient,
    init_db,
    update_patient_scan_count,
)

# Facility names for progress output
FACILITY_NAMES = {
    1: "Montana General Hospital",
    2: "Billings Regional Medical",
    3: "Missoula Community ER",
}

# -----------------------------------------------------------------------------
# Demo scans: 18 realistic cases across urgency levels and facilities
# Order: critical first, then urgent, moderate, routine (so queue looks natural)
# minutes_ago: 5 = most recent, 360 = 6 hours ago
# -----------------------------------------------------------------------------

DEMO_SCANS: List[Dict[str, Any]] = [
    # --- Critical (urgency 9-10) ---
    {
        "filename": "demo_xray_001.jpg",
        "patient_id": "P12345",
        "patient_name": "Robert Chen",
        "patient_age": 72,
        "patient_gender": "M",
        "patient_blood_type": "A+",
        "patient_medical_notes": "COPD (GOLD 3). History of recurrent pneumothorax. Home O2 2L. Medications: albuterol, tiotropium, prednisone 10mg daily. Allergies: penicillin.",
        "facility_id": 1,
        "urgency_score": 10.0,
        "conditions": [
            {"name": "Pneumothorax", "confidence": 0.95},
            {"name": "Emphysema", "confidence": 0.88},
        ],
        "reasoning": "Large pneumothorax in known COPD patient. Significant lung collapse with mediastinal shift. Immediate chest tube placement required to prevent tension physiology and cardiovascular collapse.",
        "recommended_action": "immediate",
        "risk_factors": ["respiratory_failure", "age_over_65", "COPD", "recurrent_pneumothorax"],
        "ai_confidence": "high",
        "minutes_ago": 5,
    },
    {
        "filename": "demo_xray_002.jpg",
        "patient_id": "P23456",
        "patient_name": "Margaret Holt",
        "patient_age": 68,
        "patient_gender": "F",
        "patient_blood_type": "O-",
        "patient_medical_notes": "CHF (EF 35%), HTN, DM2. Prior MI. Medications: lisinopril, metformin, furosemide 40mg, aspirin. Last admission 3 months ago for fluid overload.",
        "facility_id": 2,
        "urgency_score": 9.5,
        "conditions": [
            {"name": "Pleural_Effusion", "confidence": 0.94},
            {"name": "Cardiomegaly", "confidence": 0.91},
            {"name": "Edema", "confidence": 0.87},
        ],
        "reasoning": "Massive bilateral pleural effusions with cardiomegaly and pulmonary edema. Acute decompensated heart failure. ICU admission and diuresis required; consider thoracentesis for symptomatic relief.",
        "recommended_action": "immediate",
        "risk_factors": ["heart_failure", "age_over_65", "fluid_overload"],
        "ai_confidence": "high",
        "minutes_ago": 12,
    },
    {
        "filename": "demo_xray_003.jpg",
        "patient_id": "P34567",
        "patient_name": "James Walsh",
        "patient_age": 55,
        "patient_gender": "M",
        "patient_blood_type": "B+",
        "patient_medical_notes": "MVA today. No prior lung disease. Smoker x 20 pack-years. Medications: none. Allergies: sulfa.",
        "facility_id": 3,
        "urgency_score": 9.0,
        "conditions": [
            {"name": "Pneumothorax", "confidence": 0.92},
            {"name": "Fracture", "confidence": 0.85},
        ],
        "reasoning": "Pneumothorax with multiple rib fractures. Post-MVA. High risk of tension pneumothorax and hemothorax. Transfer to trauma center and surgical consult recommended.",
        "recommended_action": "immediate",
        "risk_factors": ["trauma", "rib_fractures", "hemothorax_risk"],
        "ai_confidence": "high",
        "minutes_ago": 18,
    },
    # --- Urgent (7-8) ---
    {
        "filename": "demo_xray_004.jpg",
        "patient_id": "P45678",
        "patient_name": "Linda Park",
        "patient_age": 61,
        "patient_gender": "F",
        "patient_blood_type": "AB+",
        "patient_medical_notes": "Type 2 DM, obesity. No prior pneumonia. Medications: metformin, losartan. Presented with fever, cough x 5 days.",
        "facility_id": 1,
        "urgency_score": 8.0,
        "conditions": [
            {"name": "Infiltration", "confidence": 0.89},
            {"name": "Pleural_Effusion", "confidence": 0.82},
            {"name": "Lung Opacity", "confidence": 0.78},
        ],
        "reasoning": "Bilateral infiltrates with parapneumonic effusion. Severe community-acquired pneumonia. Admission for IV antibiotics and monitoring; consider drainage if effusion enlarges.",
        "recommended_action": "urgent",
        "risk_factors": ["pneumonia", "effusion", "age_over_60"],
        "ai_confidence": "high",
        "minutes_ago": 28,
    },
    {
        "filename": "demo_xray_005.jpg",
        "patient_id": "P56789",
        "patient_name": "David Torres",
        "patient_age": 58,
        "patient_gender": "M",
        "patient_blood_type": "A-",
        "patient_medical_notes": "HIV on ART, CD4 420. Recent CAP. Medications: Biktarvy. Allergies: none. Follow infectious disease for empyema risk.",
        "facility_id": 2,
        "urgency_score": 7.5,
        "conditions": [
            {"name": "Pleural_Effusion", "confidence": 0.88},
            {"name": "Infiltration", "confidence": 0.75},
        ],
        "reasoning": "Large parapneumonic effusion with underlying consolidation. Risk of empyema development. Urgent drainage and infectious disease consult recommended.",
        "recommended_action": "urgent",
        "risk_factors": ["parapneumonic_effusion", "empyema_risk"],
        "ai_confidence": "high",
        "minutes_ago": 45,
    },
    {
        "filename": "demo_xray_006.jpg",
        "patient_id": "P11111",
        "patient_name": "William Gray",
        "patient_age": 74,
        "patient_gender": "M",
        "patient_blood_type": "O+",
        "patient_medical_notes": "CHF (EF 30%), afib on anticoagulation. Multiple prior admissions for volume overload. Medications: warfarin, carvedilol, furosemide 80mg.",
        "facility_id": 3,
        "urgency_score": 7.5,
        "conditions": [
            {"name": "Cardiomegaly", "confidence": 0.86},
            {"name": "Edema", "confidence": 0.81},
            {"name": "Pleural_Effusion", "confidence": 0.72},
        ],
        "reasoning": "Cardiomegaly with pulmonary edema and small effusions. CHF exacerbation in elderly patient. Urgent diuresis and cardiology evaluation; monitor for respiratory failure.",
        "recommended_action": "urgent",
        "risk_factors": ["CHF", "age_over_70", "fluid_overload"],
        "ai_confidence": "high",
        "minutes_ago": 55,
    },
    {
        "filename": "demo_xray_007.jpg",
        "patient_id": "P22222",
        "patient_name": "Susan Bell",
        "patient_age": 52,
        "patient_gender": "F",
        "patient_blood_type": "B-",
        "patient_medical_notes": "Asthma, seasonal allergies. No prior pneumonia. Medications: fluticasone/salmeterol, albuterol PRN. Presented with fever, productive cough.",
        "facility_id": 1,
        "urgency_score": 7.0,
        "conditions": [
            {"name": "Pneumonia", "confidence": 0.84},
            {"name": "Infiltration", "confidence": 0.79},
        ],
        "reasoning": "Multilobar pneumonia with moderate consolidation. Febrile and hypoxic. Admission for IV antibiotics and oxygen; rule out sepsis.",
        "recommended_action": "urgent",
        "risk_factors": ["pneumonia", "multilobar", "hypoxia"],
        "ai_confidence": "high",
        "minutes_ago": 72,
    },
    # --- Moderate (5-6) ---
    {
        "filename": "demo_xray_008.jpg",
        "patient_id": "P67890",
        "patient_name": "Michael Reed",
        "patient_age": 48,
        "patient_gender": "M",
        "patient_blood_type": "A+",
        "patient_medical_notes": "Healthy. Smoker x 10 pack-years. Presented with cough, mild fever x 3 days. No prior lung disease.",
        "facility_id": 2,
        "urgency_score": 6.0,
        "conditions": [
            {"name": "Infiltration", "confidence": 0.76},
            {"name": "Lung Opacity", "confidence": 0.68},
        ],
        "reasoning": "Mild right lower lobe infiltrate. Community-acquired pneumonia, likely bacterial. Outpatient antibiotics and follow-up in 48-72 hours appropriate if clinically stable.",
        "recommended_action": "urgent",
        "risk_factors": ["pneumonia", "mild"],
        "ai_confidence": "medium",
        "minutes_ago": 95,
    },
    {
        "filename": "demo_xray_009.jpg",
        "patient_id": "P78901",
        "patient_name": "Patricia Hayes",
        "patient_age": 52,
        "patient_gender": "F",
        "patient_blood_type": "O+",
        "patient_medical_notes": "Hypothyroidism on levothyroxine. Recent URI. Small effusion on prior CXR 2 weeks ago; follow-up today.",
        "facility_id": 3,
        "urgency_score": 5.5,
        "conditions": [
            {"name": "Pleural_Effusion", "confidence": 0.71},
            {"name": "Atelectasis", "confidence": 0.65},
        ],
        "reasoning": "Small unilateral pleural effusion with basilar atelectasis. Likely viral or reactive. Conservative management and repeat imaging in 1-2 weeks if persistent.",
        "recommended_action": "urgent",
        "risk_factors": ["small_effusion", "atelectasis"],
        "ai_confidence": "medium",
        "minutes_ago": 110,
    },
    {
        "filename": "demo_xray_010.jpg",
        "patient_id": "P33333",
        "patient_name": "Richard Fox",
        "patient_age": 59,
        "patient_gender": "M",
        "patient_blood_type": "AB-",
        "patient_medical_notes": "HTN, hyperlipidemia. No known heart failure. Dyspnea on exertion x 2 weeks. Medications: amlodipine, atorvastatin.",
        "facility_id": 1,
        "urgency_score": 6.0,
        "conditions": [
            {"name": "Cardiomegaly", "confidence": 0.78},
            {"name": "Pleural_Effusion", "confidence": 0.62},
        ],
        "reasoning": "Cardiomegaly with small bilateral effusions. Possible early CHF or pericardial process. Cardiology referral and echocardiogram; diuretics if volume overload confirmed.",
        "recommended_action": "urgent",
        "risk_factors": ["cardiomegaly", "effusion", "age_50s"],
        "ai_confidence": "medium",
        "minutes_ago": 130,
    },
    {
        "filename": "demo_xray_011.jpg",
        "patient_id": "P44444",
        "patient_name": "Nancy Cole",
        "patient_age": 44,
        "patient_gender": "F",
        "patient_blood_type": "A-",
        "patient_medical_notes": "Otherwise healthy. Cough, low-grade fever x 5 days. No immunosuppression. Started OTC cold meds.",
        "facility_id": 2,
        "urgency_score": 5.5,
        "conditions": [
            {"name": "Infiltration", "confidence": 0.69},
            {"name": "Atelectasis", "confidence": 0.58},
        ],
        "reasoning": "Patchy infiltrate with subsegmental atelectasis. Atypical pneumonia or early bacterial process. Oral antibiotics and recheck if no improvement in 48 hours.",
        "recommended_action": "urgent",
        "risk_factors": ["infiltrate", "atelectasis"],
        "ai_confidence": "medium",
        "minutes_ago": 155,
    },
    {
        "filename": "demo_xray_012.jpg",
        "patient_id": "P55555",
        "patient_name": "Thomas King",
        "patient_age": 56,
        "patient_gender": "M",
        "patient_blood_type": "O-",
        "patient_medical_notes": "Former smoker, quit 5 years ago. Incidental nodule on prior CT 1 year ago; surveillance imaging today. No constitutional symptoms.",
        "facility_id": 3,
        "urgency_score": 5.0,
        "conditions": [
            {"name": "Nodule", "confidence": 0.72},
            {"name": "Lung Opacity", "confidence": 0.55},
        ],
        "reasoning": "Solitary pulmonary nodule with mild surrounding opacity. Requires CT for characterization and follow-up protocol. No acute intervention; outpatient CT and pulmonary referral.",
        "recommended_action": "urgent",
        "risk_factors": ["nodule", "follow_up_required"],
        "ai_confidence": "medium",
        "minutes_ago": 180,
    },
    # --- Routine (1-4) ---
    {
        "filename": "demo_xray_013.jpg",
        "patient_id": "P89012",
        "patient_name": "Daniel Scott",
        "patient_age": 35,
        "patient_gender": "M",
        "patient_blood_type": "B+",
        "patient_medical_notes": "Post-op day 2 appendectomy. No lung history. Incentive spirometry in use. Mild atelectasis on prior film.",
        "facility_id": 1,
        "urgency_score": 3.0,
        "conditions": [
            {"name": "Atelectasis", "confidence": 0.68},
        ],
        "reasoning": "Subsegmental atelectasis at left base. Post-operative finding. Incentive spirometry and early mobilization recommended. No acute pathology.",
        "recommended_action": "routine",
        "risk_factors": ["post_op", "atelectasis"],
        "ai_confidence": "medium",
        "minutes_ago": 210,
    },
    {
        "filename": "demo_xray_014.jpg",
        "patient_id": "P90123",
        "patient_name": "Jennifer Adams",
        "patient_age": 42,
        "patient_gender": "F",
        "patient_blood_type": "A+",
        "patient_medical_notes": "Pre-op CXR for elective cholecystectomy. No respiratory symptoms. No significant PMH. Medications: none.",
        "facility_id": 2,
        "urgency_score": 2.0,
        "conditions": [],
        "reasoning": "No significant findings. Pre-operative chest X-ray clearance. No contraindications to surgery. Lungs are clear.",
        "recommended_action": "routine",
        "risk_factors": [],
        "ai_confidence": "high",
        "minutes_ago": 240,
    },
    {
        "filename": "demo_xray_015.jpg",
        "patient_id": "P66666",
        "patient_name": "Christopher Hill",
        "patient_age": 38,
        "patient_gender": "M",
        "patient_blood_type": "O+",
        "patient_medical_notes": "Mild asthma. Occasional inhaler use. Chronic right pleural thickening on prior films; stable. No acute complaints.",
        "facility_id": 3,
        "urgency_score": 3.5,
        "conditions": [
            {"name": "Atelectasis", "confidence": 0.55},
            {"name": "Pleural_Thickening", "confidence": 0.48},
        ],
        "reasoning": "Minimal basilar atelectasis and pleural thickening. Chronic/reactive changes. No acute process. Routine follow-up if clinically indicated.",
        "recommended_action": "routine",
        "risk_factors": ["chronic_changes"],
        "ai_confidence": "low",
        "minutes_ago": 275,
    },
    {
        "filename": "demo_xray_016.jpg",
        "patient_id": "P77777",
        "patient_name": "Emily Brooks",
        "patient_age": 29,
        "patient_gender": "F",
        "patient_blood_type": "AB+",
        "patient_medical_notes": "Healthy. CXR for clearance (e.g. work or travel). No cough, fever, or dyspnea. No PMH.",
        "facility_id": 1,
        "urgency_score": 2.5,
        "conditions": [],
        "reasoning": "Normal chest X-ray. No focal consolidation, effusion, or pneumothorax. Clear for discharge or next step in workup.",
        "recommended_action": "routine",
        "risk_factors": [],
        "ai_confidence": "high",
        "minutes_ago": 300,
    },
    {
        "filename": "demo_xray_017.jpg",
        "patient_id": "P88888",
        "patient_name": "Joseph Wright",
        "patient_age": 51,
        "patient_gender": "M",
        "patient_blood_type": "B-",
        "patient_medical_notes": "HTN. Known cardiomegaly on prior imaging; cardiology follow-up. Stable. Medications: lisinopril.",
        "facility_id": 2,
        "urgency_score": 4.0,
        "conditions": [
            {"name": "Cardiomegaly", "confidence": 0.62},
        ],
        "reasoning": "Mild cardiomegaly. Stable chronic finding. Cardiology follow-up for routine evaluation. No acute intervention required.",
        "recommended_action": "routine",
        "risk_factors": ["cardiomegaly", "chronic"],
        "ai_confidence": "medium",
        "minutes_ago": 330,
    },
    {
        "filename": "demo_xray_018.jpg",
        "patient_id": "P99999",
        "patient_name": "Barbara Foster",
        "patient_age": 63,
        "patient_gender": "F",
        "patient_blood_type": "O+",
        "patient_medical_notes": "COPD (GOLD 2). Baseline hyperinflation. On Advair, prn albuterol. No recent exacerbation. Routine CXR for chronic care.",
        "facility_id": 3,
        "urgency_score": 4.0,
        "conditions": [
            {"name": "Emphysema", "confidence": 0.70},
        ],
        "reasoning": "Hyperinflation and emphysematous changes. Known COPD. No acute process. Continue home regimen; ensure vaccinations and inhaler compliance.",
        "recommended_action": "routine",
        "risk_factors": ["COPD", "emphysema"],
        "ai_confidence": "medium",
        "minutes_ago": 360,
    },
]


def main() -> None:
    """Initialize DB and seed demo scans with staggered timestamps."""
    print("Initializing database...")
    init_db()
    print("✅ Database ready\n")
    print("Seeding demo scans...")

    now = datetime.now()
    patients_seen: set = set()
    urgency_min, urgency_max = 10.0, 0.0

    for scan in DEMO_SCANS:
        # Get or create patient (with name, blood_type, medical_notes for frontend display)
        patient_db_id = get_or_create_patient(
            patient_identifier=scan["patient_id"],
            age=scan["patient_age"],
            gender=scan["patient_gender"],
            name=scan.get("patient_name"),
            blood_type=scan.get("patient_blood_type"),
            medical_notes=scan.get("patient_medical_notes"),
        )
        patients_seen.add(scan["patient_id"])

        # Timestamp: N minutes ago
        upload_dt = now - timedelta(minutes=scan["minutes_ago"])
        upload_time_str = upload_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Insert scan with explicit upload_time
        scan_id = add_scan(
            filename=scan["filename"],
            facility_id=scan["facility_id"],
            urgency_score=scan["urgency_score"],
            conditions=scan["conditions"],
            image_path=f"uploads/{scan['filename']}",
            heatmap_path=None,
            reasoning=scan["reasoning"],
            recommended_action=scan["recommended_action"],
            risk_factors=scan["risk_factors"],
            ai_confidence=scan["ai_confidence"],
            patient_id=patient_db_id,
            upload_time=upload_time_str,
        )

        update_patient_scan_count(patient_db_id)

        facility_name = FACILITY_NAMES.get(scan["facility_id"], "Unknown")
        print(
            f"✅ Added scan {scan_id}: {scan['filename']} (urgency: {scan['urgency_score']}) "
            f"- {scan['patient_id']} at {facility_name}"
        )
        urgency_min = min(urgency_min, scan["urgency_score"])
        urgency_max = max(urgency_max, scan["urgency_score"])

    print("\nSummary:")
    print(f"✅ Seeded {len(DEMO_SCANS)} demo scans")
    print(f"✅ Created/reused {len(patients_seen)} patients")
    print("✅ Across 3 facilities")
    print(f"✅ Urgency range: {urgency_min} - {urgency_max}")
    print("\nTest the queue:")
    print("  curl http://127.0.0.1:5001/queue | python3 -m json.tool")


if __name__ == "__main__":
    main()
