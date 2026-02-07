"""
AI model module for chest X-ray triage using torchxrayvision DenseNet121.

Loads a pre-trained model once (singleton), runs inference on uploaded images,
and returns detected conditions with urgency scores for prioritization.

NOTE: This module is named xray_model (not model) to avoid shadowing
torchxrayvision's internal 'model' package. Use: from xray_model import get_model
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import torch
from PIL import Image

# torchxrayvision must be imported after torch
import torchxrayvision as xrv

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Urgency mapping: condition name -> urgency score (1-10)
# Aligned with torchxrayvision "all" model pathology names.
# Default for unmapped conditions is 3.
# -----------------------------------------------------------------------------
URGENCY_MAP: Dict[str, int] = {
    "Pneumothorax": 10,           # Critical - life-threatening
    "Edema": 8,                   # Very urgent
    "Effusion": 7,                # Pleural effusion - urgent (library uses "Effusion")
    "Infiltration": 6,            # Moderately urgent
    "Pneumonia": 6,
    "Consolidation": 6,
    "Lung Opacity": 6,
    "Cardiomegaly": 4,            # Less urgent
    "Enlarged Cardiomediastinum": 4,
    "Atelectasis": 3,
    "Mass": 5,
    "Nodule": 4,
    "Pleural_Thickening": 4,
    "Emphysema": 4,
    "Fibrosis": 3,
    "Hernia": 3,
    "Lung Lesion": 5,
    "Fracture": 6,
}

DEFAULT_URGENCY = 3
CONFIDENCE_THRESHOLD = 0.5


class XRayModel:
    """
    Wrapper for torchxrayvision DenseNet121 chest X-ray model.

    Handles image preprocessing (grayscale, 224x224, normalization to [-1024, 1024]),
    inference, and mapping of predictions to conditions with urgency scores.
    """

    def __init__(self) -> None:
        """
        Load the DenseNet121 model with weights trained on multiple chest X-ray datasets.
        Model expects input in [-1024, 1024] range at 224x224 (grayscale).
        """
        try:
            self._model = xrv.models.DenseNet(weights="densenet121-res224-all")
            self._model.eval()
            # Model may have .pathologies or .targets (same list when weights loaded)
            self._pathology_names: List[str] = getattr(
                self._model, "pathologies", getattr(self._model, "targets", [])
            )
            logger.info(
                "XRayModel loaded successfully with %d pathologies",
                len(self._pathology_names),
            )
        except Exception as e:
            logger.exception("Failed to load torchxrayvision DenseNet model")
            raise RuntimeError(f"Could not load AI model: {e}") from e

    def preprocess_image(self, image_path: str) -> torch.Tensor:
        """
        Load image from path, convert to grayscale, resize to 224x224,
        and normalize to [-1024, 1024] as expected by torchxrayvision.

        Args:
            image_path: Path to the image file (e.g. jpg, png).

        Returns:
            Tensor of shape (1, 1, 224, 224) with values in [-1024, 1024].

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the image cannot be read or has invalid format.
        """
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        try:
            img = Image.open(path)
            img.load()
        except Exception as e:
            raise ValueError(f"Cannot open image at {image_path}: {e}") from e

        try:
            # Convert to grayscale (mode 'L') if RGB or RGBA
            if img.mode != "L":
                img = img.convert("L")
            arr = np.array(img, dtype=np.float32)
        except Exception as e:
            raise ValueError(f"Failed to convert image to array: {e}") from e

        if arr.size == 0 or arr.ndim < 2:
            raise ValueError("Image is empty or has invalid dimensions")

        # Take first channel if multi-channel (should not happen after L conversion)
        if arr.ndim > 2:
            arr = arr[:, :, 0]

        # Resize to 224x224 using PIL for consistency
        img_resized = Image.fromarray(arr.astype(np.uint8) if arr.max() <= 255 else arr)
        img_resized = img_resized.resize((224, 224), Image.BILINEAR)
        arr = np.array(img_resized, dtype=np.float32)

        # Normalize to [-1024, 1024] as expected by torchxrayvision
        # Formula: (2 * (img / maxval) - 1) * 1024  ->  0 -> -1024, 255 -> 1024
        maxval = float(max(arr.max(), 1.0))
        arr = (2.0 * (arr / maxval) - 1.0) * 1024.0

        # Shape: (1, 1, 224, 224) for batch=1, channel=1, H, W
        tensor = torch.from_numpy(arr).float().unsqueeze(0).unsqueeze(0)
        return tensor

    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Run inference on an image and return detected conditions with urgency.

        Args:
            image_path: Path to the chest X-ray image.

        Returns:
            Dict with:
                - conditions: List of {"name", "confidence", "urgency"} for scores >= threshold.
                - urgency_score: Max urgency among detected conditions (0 if none).
                - all_predictions: Dict of pathology -> score for debugging.
        """
        try:
            x = self.preprocess_image(image_path)
        except (FileNotFoundError, ValueError) as e:
            logger.warning("Preprocessing failed for %s: %s", image_path, e)
            raise

        try:
            with torch.no_grad():
                out = self._model(x)
            # Handle both raw logits and pre-calibrated outputs (model may apply sigmoid + op_norm)
            if out.dim() == 2:
                scores = out[0].detach().cpu().numpy()
            else:
                scores = out.detach().cpu().numpy().flatten()
        except Exception as e:
            logger.exception("Inference failed for %s", image_path)
            raise RuntimeError(f"Inference failed: {e}") from e

        # Build pathology -> score map; ensure we have one score per pathology name
        pathology_names = self._pathology_names
        if len(scores) != len(pathology_names):
            logger.warning(
                "Score length %d != pathology length %d; truncating or padding",
                len(scores),
                len(pathology_names),
            )
            min_len = min(len(scores), len(pathology_names))
            scores = scores[:min_len]
            pathology_names = pathology_names[:min_len]

        # If model returns logits (no op_threshs), apply sigmoid for 0-1 confidence
        if scores.min() < 0 or scores.max() > 1.0:
            scores = 1.0 / (1.0 + np.exp(-np.clip(scores, -500, 500)))

        all_predictions = {}
        conditions: List[Dict[str, Any]] = []

        for name, score in zip(pathology_names, scores):
            if not name or not name.strip():
                continue
            score = float(score)
            all_predictions[name] = score

            if score >= CONFIDENCE_THRESHOLD:
                urgency = URGENCY_MAP.get(name, DEFAULT_URGENCY)
                conditions.append({
                    "name": name,
                    "confidence": round(score, 4),
                    "urgency": urgency,
                })

        # Urgency score is max urgency among detected conditions, or 0 if none
        urgency_score = float(
            max((c["urgency"] for c in conditions), default=0)
        )

        return {
            "conditions": conditions,
            "urgency_score": urgency_score,
            "all_predictions": all_predictions,
        }

    def predict_with_reasoning(
        self,
        image_path: str,
        facility_name: str = "Unknown",
        queue_length: int = 0,
    ) -> Dict[str, Any]:
        """
        Enhanced prediction with LLM clinical reasoning (Gemini).

        Combines torchxrayvision detection with Gemini urgency assessment,
        reasoning, and recommended action. Falls back to basic predict if
        Gemini is unavailable.

        Args:
            image_path: Path to the chest X-ray image.
            facility_name: Facility name for context.
            queue_length: Current queue length for context.

        Returns:
            Dict with conditions, urgency_score, reasoning, recommended_action,
            risk_factors, confidence, and all_predictions.
        """
        basic_result = self.predict(image_path)
        try:
            from llm_triage import get_triage_client

            triage = get_triage_client()
            gemini_assessment = triage.assess_urgency(
                conditions=basic_result["conditions"],
                facility_name=facility_name,
                queue_length=queue_length,
            )
            return {
                "conditions": basic_result["conditions"],
                "urgency_score": gemini_assessment["urgency_score"],
                "reasoning": gemini_assessment["reasoning"],
                "recommended_action": gemini_assessment["recommended_action"],
                "risk_factors": gemini_assessment.get("risk_factors", []),
                "confidence": gemini_assessment.get("confidence", "medium"),
                "all_predictions": basic_result["all_predictions"],
            }
        except Exception as e:
            logger.warning("LLM reasoning failed, using fallback: %s", e)
            # Add fallback fields so API/DB still get structure
            urgency = basic_result["urgency_score"]
            action = "immediate" if urgency >= 9 else ("urgent" if urgency >= 7 else "routine")
            return {
                "conditions": basic_result["conditions"],
                "urgency_score": basic_result["urgency_score"],
                "reasoning": f"Fallback: no LLM available. Rule-based urgency {urgency}.",
                "recommended_action": action,
                "risk_factors": [c.get("name", "") for c in basic_result["conditions"] if c.get("name")],
                "confidence": "low",
                "all_predictions": basic_result["all_predictions"],
            }

    def predict_with_hybrid_rag(
        self,
        image_path: str,
        facility_name: str = "Montana General Hospital",
        queue_length: int = 0,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Prediction with HYBRID RAG reasoning (hospital + patient).

        Args:
            image_path: Path to X-ray image
            facility_name: Hospital name
            queue_length: Current queue length
            patient_id: Optional patient identifier for history lookup

        Returns:
            Dict with conditions, urgency_score, reasoning, recommended_action,
            risk_factors, confidence, rag_enabled, hospital_cases_used,
            patient_history_found, all_predictions.
        """
        basic_result = self.predict(image_path)
        try:
            from llm_triage import get_triage_client

            triage = get_triage_client()
            hybrid_assessment = triage.assess_urgency_hybrid_rag(
                conditions=basic_result["conditions"],
                facility_name=facility_name,
                queue_length=queue_length,
                patient_id=patient_id,
            )
            return {
                "conditions": basic_result["conditions"],
                "urgency_score": hybrid_assessment["urgency_score"],
                "reasoning": hybrid_assessment["reasoning"],
                "recommended_action": hybrid_assessment["recommended_action"],
                "risk_factors": hybrid_assessment.get("risk_factors", []),
                "confidence": hybrid_assessment.get("confidence", "medium"),
                "rag_enabled": hybrid_assessment.get("rag_enabled", False),
                "hospital_cases_used": hybrid_assessment.get("hospital_cases_used", 0),
                "patient_history_found": hybrid_assessment.get(
                    "patient_history_found", False
                ),
                "all_predictions": basic_result["all_predictions"],
            }
        except Exception as e:
            logger.warning("Error in hybrid RAG: %s", e)
            urgency = basic_result["urgency_score"]
            action = (
                "immediate"
                if urgency >= 9
                else ("urgent" if urgency >= 7 else "routine")
            )
            return {
                "conditions": basic_result["conditions"],
                "urgency_score": urgency,
                "reasoning": f"Fallback: hybrid RAG failed. Rule-based urgency {urgency}.",
                "recommended_action": action,
                "risk_factors": [
                    c.get("name", "") for c in basic_result["conditions"] if c.get("name")
                ],
                "confidence": "low",
                "rag_enabled": False,
                "hospital_cases_used": 0,
                "patient_history_found": False,
                "all_predictions": basic_result["all_predictions"],
            }

    def get_heatmap(self, image_path: str) -> str:
        """
        Return path to visualization for the scan (heatmap or original image).

        Placeholder: returns the original image path. GradCAM can be added later
        if time permits during the hackathon.

        Args:
            image_path: Path to the chest X-ray image.

        Returns:
            Path to the image to display (currently the same as input).
        """
        # TODO: Implement GradCAM if time permits during hackathon
        return image_path


# -----------------------------------------------------------------------------
# Singleton: load model once, reuse for all requests
# -----------------------------------------------------------------------------
_model_instance: Optional[XRayModel] = None


def get_model() -> XRayModel:
    """
    Return the global XRayModel instance, loading it on first call.

    Returns:
        The singleton XRayModel instance.

    Raises:
        RuntimeError: If the model fails to load.
    """
    global _model_instance
    if _model_instance is None:
        _model_instance = XRayModel()
    return _model_instance
