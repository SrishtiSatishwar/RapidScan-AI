"""
LLM-enhanced clinical reasoning for X-ray triage using Google Gemini.

Provides contextual urgency assessment, reasoning, and recommended actions
instead of hardcoded lookup. Falls back to rule-based scoring if API fails.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Lazy import so backend works without Gemini when key is missing
genai = None


def _get_genai():
    global genai
    if genai is None:
        import google.generativeai as _genai
        genai = _genai
    return genai


class GeminiTriage:
    """
    Clinical reasoning engine using Google Gemini for intelligent urgency assessment.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """
        Initialize Gemini client.

        Args:
            api_key: Gemini API key (reads from GEMINI_API_KEY env var if not provided).
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment or parameter")
        _get_genai().configure(api_key=self.api_key)
        # Use a current model: gemini-1.5-flash was deprecated (404). Prefer 2.0/2.5.
        model_id = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.model = _get_genai().GenerativeModel(model_id)

    def assess_urgency(
        self,
        conditions: List[Dict],
        facility_name: str,
        queue_length: int = 0,
        patient_context: Optional[Dict] = None,
    ) -> Dict:
        """
        Assess clinical urgency using Gemini reasoning.

        Args:
            conditions: List of detected conditions from torchxrayvision
                       e.g. [{"name": "Pneumothorax", "confidence": 0.92}, ...]
            facility_name: Name of the facility (for context).
            queue_length: Number of scans currently in queue.
            patient_context: Optional additional context (age, symptoms, etc.).

        Returns:
            Dict with urgency_score, reasoning, recommended_action, risk_factors, confidence.
        """
        prompt = self._build_prompt(
            conditions, facility_name, queue_length, patient_context
        )
        try:
            response = self.model.generate_content(prompt)
            text = response.text if hasattr(response, "text") else str(response)
            if not text:
                raise ValueError("Empty response from Gemini")
            return self._parse_response(text)
        except Exception as e:
            logger.warning("Gemini API error: %s", e)
            return self._fallback_urgency(conditions)

    def _build_prompt(
        self,
        conditions: List[Dict],
        facility_name: str,
        queue_length: int,
        patient_context: Optional[Dict],
    ) -> str:
        """Build structured prompt for Gemini."""
        findings_text = "\n".join(
            [f"- {c['name']}: {c.get('confidence', 0):.2f} confidence" for c in conditions]
        )
        if not findings_text:
            findings_text = "- No significant findings detected (appears normal)"

        context_text = (
            f"Facility: {facility_name} (rural hospital with limited ICU/specialist resources)\n"
            f"Current queue: {queue_length} scans waiting\n"
            f"Time: {datetime.now().strftime('%H:%M on %A')}\n"
        )
        if patient_context:
            context_text += f"Patient context: {patient_context}\n"

        prompt = f"""You are an expert radiologist assistant evaluating chest X-ray findings for emergency triage in a rural hospital setting.

DETECTED FINDINGS FROM AI ANALYSIS:
{findings_text}

CLINICAL CONTEXT:
{context_text}

TASK:
Assess the clinical urgency of this case on a scale of 1-10 and provide clear reasoning.

CONSIDERATIONS:
1. Life-threatening potential of findings
2. Time-sensitivity of required treatment
3. Resource constraints in rural setting (limited ICU, specialists may need transfer)
4. Combination effects if multiple findings present
5. Current queue length and wait time implications
6. Probability that findings require immediate intervention vs. can wait for routine review

URGENCY SCALE:
- 9-10: Immediate life threat (pneumothorax, massive hemorrhage, etc.) - see within 5-10 minutes
- 7-8: Urgent findings requiring rapid intervention (large effusion, significant pneumonia, etc.) - see within 30-60 minutes
- 5-6: Moderate findings needing attention but not immediately critical - see within 2-4 hours
- 3-4: Minor findings, routine follow-up sufficient - see within 8-12 hours
- 1-2: No significant findings or incidental findings only - routine review

Respond ONLY with valid JSON in this exact format (no markdown, no code blocks, just raw JSON):
{{
  "urgency_score": <number between 1-10>,
  "reasoning": "<2-3 sentence clinical explanation of urgency assessment>",
  "recommended_action": "<one of: immediate | urgent | routine>",
  "risk_factors": ["<factor1>", "<factor2>", ...],
  "confidence": "<one of: high | medium | low>"
}}

JSON response:"""
        return prompt

    def _parse_response(self, response_text: str) -> Dict:
        """Parse Gemini JSON response; fallback to default structure on failure."""
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            if len(parts) >= 2:
                block = parts[1]
                if block.lower().startswith("json"):
                    block = block[4:]
                cleaned = block.strip()
        try:
            result = json.loads(cleaned)
            for field in ("urgency_score", "reasoning", "recommended_action", "risk_factors"):
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
            result["urgency_score"] = float(result["urgency_score"])
            result["urgency_score"] = max(1.0, min(10.0, result["urgency_score"]))
            if "confidence" not in result:
                result["confidence"] = "medium"
            return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse Gemini response: %s", e)
            return {
                "urgency_score": 5.0,
                "reasoning": "Unable to parse AI reasoning. Using default urgency.",
                "recommended_action": "urgent",
                "risk_factors": ["parsing_error"],
                "confidence": "low",
            }

    def assess_urgency_hybrid_rag(
        self,
        conditions: List[Dict],
        facility_name: str,
        queue_length: int = 0,
        patient_id: Optional[str] = None,
        patient_context: Optional[Dict] = None,
    ) -> Dict:
        """
        Assess urgency with HYBRID RAG (hospital patterns + patient history).

        Args:
            conditions: Detected conditions from torchxrayvision
            facility_name: Hospital name
            queue_length: Current queue length
            patient_id: Optional patient identifier for history lookup
            patient_context: Optional additional patient info

        Returns:
            Dict with urgency_score, reasoning, recommended_action, risk_factors,
            confidence, plus RAG metadata (hospital_cases_used, patient_history_found)
        """
        rag_context: Dict = {"hospital_cases": [], "patient_history": None}
        try:
            from weaviate_store import get_rag_store

            store = get_rag_store()
            condition_names = [c.get("name", "") for c in conditions if c.get("name")]
            hospital_cases = store.find_similar_hospital_cases(
                condition_names, n_results=3
            )
            rag_context["hospital_cases"] = hospital_cases
            if patient_id:
                patient_history = store.get_patient_history(patient_id)
                rag_context["patient_history"] = patient_history
                logger.info(
                    "Patient history %s for %s",
                    "found" if patient_history else "not found",
                    patient_id,
                )
        except Exception as e:
            logger.warning("RAG query failed: %s", e)

        prompt = self._build_hybrid_rag_prompt(
            conditions, facility_name, queue_length, patient_context, rag_context
        )
        try:
            response = self.model.generate_content(prompt)
            text = response.text if hasattr(response, "text") else str(response)
            if not text:
                raise ValueError("Empty response from Gemini")
            result = self._parse_response(text)
            result["rag_enabled"] = True
            result["hospital_cases_used"] = len(rag_context["hospital_cases"])
            result["patient_history_found"] = rag_context["patient_history"] is not None
            return result
        except Exception as e:
            logger.warning("Gemini error in hybrid RAG: %s", e)
            fallback = self._fallback_urgency(conditions)
            fallback["rag_enabled"] = True
            fallback["hospital_cases_used"] = len(rag_context["hospital_cases"])
            fallback["patient_history_found"] = rag_context["patient_history"] is not None
            return fallback

    def _build_hybrid_rag_prompt(
        self,
        conditions: List[Dict],
        facility_name: str,
        queue_length: int,
        patient_context: Optional[Dict],
        rag_context: Dict,
    ) -> str:
        """
        Build Gemini prompt with BOTH hospital and patient context.
        """
        base = self._build_prompt(
            conditions, facility_name, queue_length, patient_context
        )
        hospital_section = ""
        if rag_context.get("hospital_cases"):
            hospital_section = "\n\nHOSPITAL PATTERNS - Historical Cases:\n"
            hospital_section += "=" * 60 + "\n"
            for i, case in enumerate(rag_context["hospital_cases"], 1):
                sim = case.get("similarity", 0)
                hospital_section += f"\nCase {i} (similarity: {sim:.2f}):\n"
                hospital_section += f"  Conditions: {', '.join(case.get('conditions', []))}\n"
                hospital_section += f"  Urgency: {case.get('urgency_score', 0)}/10\n"
                hospital_section += f"  Outcome: {case.get('outcome', 'Unknown')}\n"
                hospital_section += f"  Time to treatment: {case.get('time_to_treatment_minutes', 0)} minutes\n"
                if case.get("complications"):
                    hospital_section += f"  Complications: {', '.join(case['complications'])}\n"
                if case.get("clinical_notes"):
                    hospital_section += f"  Notes: {case['clinical_notes']}\n"
            hospital_section += "\n" + "=" * 60 + "\n"

        patient_hist = rag_context.get("patient_history")
        patient_section = ""
        if patient_hist:
            patient_section = "\n\nPATIENT-SPECIFIC CONTEXT - Individual Risk Profile:\n"
            patient_section += "=" * 60 + "\n"
            demographics = patient_hist.get("demographics", {})
            patient_section += "\nDemographics:\n"
            patient_section += f"  Age: {demographics.get('age', 'Unknown')}\n"
            patient_section += f"  Gender: {demographics.get('gender', 'Unknown')}\n"
            chronic = patient_hist.get("chronic_conditions", [])
            if chronic:
                patient_section += f"\nChronic Conditions: {', '.join(chronic)}\n"
                patient_section += "  ⚠️ These increase baseline risk significantly\n"
            risks = patient_hist.get("risk_factors", [])
            if risks:
                patient_section += f"\nRisk Factors: {', '.join(risks)}\n"
            scan_history = patient_hist.get("scan_history", [])
            if scan_history:
                patient_section += f"\nPrevious Scans ({len(scan_history)} total):\n"
                for scan in scan_history[:3]:
                    patient_section += f"  - {scan.get('date')}: {', '.join(scan.get('findings', []))}\n"
                    patient_section += f"    Outcome: {scan.get('outcome', 'Unknown')}\n"
                    if scan.get("complications"):
                        patient_section += f"    Complications: {', '.join(scan['complications'])}\n"
            patient_section += "\n" + "=" * 60 + "\n"
            patient_section += "\n⚠️ CRITICAL: This patient has documented history.\n"
            age = demographics.get("age") if isinstance(demographics.get("age"), (int, float)) else 0
            if age and int(age) > 65:
                patient_section += f"⚠️ ELDERLY PATIENT (age {age}): Significantly higher risk.\n"
            if chronic:
                patient_section += f"⚠️ COMORBIDITIES PRESENT: {len(chronic)} chronic conditions increase urgency.\n"
            if any(scan.get("complications") for scan in scan_history):
                patient_section += "⚠️ PREVIOUS COMPLICATIONS: History of adverse outcomes. Err on side of caution.\n"
            patient_section += "\n"
        else:
            patient_section = "\n\nPATIENT CONTEXT: New patient, no previous history available.\n"
            patient_section += "Assessment based on current findings and hospital patterns only.\n\n"

        instructions = """
ASSESSMENT INSTRUCTIONS:
1. Start with hospital pattern baseline urgency
2. If patient has comorbidities (COPD, CHF, diabetes), ADD 1-2 points
3. If patient is elderly (>65), ADD 0.5-1 point
4. If patient has history of complications with this condition, ADD 1-2 points
5. If patient is young (<40) and healthy with no history, SUBTRACT 0.5-1 point
6. Consider: Same finding = different urgency based on patient risk

Final urgency should reflect BOTH what usually happens (hospital patterns)
AND this specific patient's risk profile.

"""
        insert = hospital_section + patient_section + instructions + "\nJSON response:"
        enhanced = base.replace("JSON response:", insert)
        return enhanced

    def _fallback_urgency(self, conditions: List[Dict]) -> Dict:
        """Fallback urgency when Gemini is unavailable; uses hardcoded map."""
        URGENCY_MAP = {
            "Pneumothorax": 10,
            "Edema": 8,
            "Effusion": 7,
            "Pleural_Effusion": 7,
            "Infiltration": 6,
            "Pneumonia": 6,
            "Consolidation": 6,
            "Lung Opacity": 6,
            "Cardiomegaly": 4,
            "Atelectasis": 3,
            "Mass": 5,
            "Nodule": 4,
        }
        if not conditions:
            return {
                "urgency_score": 0.0,
                "reasoning": "No significant findings detected.",
                "recommended_action": "routine",
                "risk_factors": [],
                "confidence": "medium",
            }
        urgency = max(
            (URGENCY_MAP.get(c.get("name", ""), 3) for c in conditions),
            default=3,
        )
        top = max(
            conditions,
            key=lambda c: URGENCY_MAP.get(c.get("name", ""), 3),
        )
        reasoning = (
            f"Detected {top.get('name', 'finding')} with {top.get('confidence', 0):.2f} confidence. "
            "Using fallback urgency (Gemini unavailable)."
        )
        return {
            "urgency_score": float(urgency),
            "reasoning": reasoning,
            "recommended_action": "immediate" if urgency >= 9 else ("urgent" if urgency >= 7 else "routine"),
            "risk_factors": [c.get("name", "") for c in conditions if c.get("name")],
            "confidence": "medium",
        }


_triage_instance: Optional[GeminiTriage] = None


def get_triage_client(api_key: Optional[str] = None) -> GeminiTriage:
    """Get or create GeminiTriage singleton."""
    global _triage_instance
    if _triage_instance is None:
        _triage_instance = GeminiTriage(api_key=api_key)
    return _triage_instance
