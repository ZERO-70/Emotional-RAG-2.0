"""Advanced emotion detection using transformer models.

Phase 2 enhancement providing:
- 7 fine-grained emotions with confidence scores
- Multi-label emotion detection
- Better accuracy than keyword-based approach
- Fallback to keyword detection for reliability
"""

import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass

try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    pipeline = None

from app.core.config import settings
from app.services.emotion_tracker import EmotionTracker  # Fallback

logger = logging.getLogger(__name__)


@dataclass
class EmotionPrediction:
    """Emotion prediction with confidence score."""
    emotion: str
    confidence: float
    all_scores: Dict[str, float]


class TransformerEmotionDetector:
    """Transformer-based emotion classification.
    
    Uses j-hartmann/emotion-english-distilroberta-base:
    - 7 emotions: anger, disgust, fear, joy, neutral, sadness, surprise
    - Confidence scores for each emotion
    - ~66% accuracy on balanced test set
    - Falls back to keyword detection if unavailable
    """
    
    # Emotion to importance weight mapping
    EMOTION_WEIGHTS = {
        "anger": 0.9,
        "disgust": 0.8,
        "fear": 0.85,
        "joy": 0.7,
        "neutral": 0.3,
        "sadness": 0.75,
        "surprise": 0.6
    }
    
    def __init__(self, model_name: str = None):
        """Initialize transformer emotion detector.
        
        Args:
            model_name: HuggingFace model name (default from settings)
        """
        self.model_name = model_name or settings.emotion_model
        self.threshold = settings.emotion_confidence_threshold
        self.classifier = None
        self.fallback_detector = EmotionTracker()  # Keyword-based fallback
        
        if not TRANSFORMERS_AVAILABLE:
            logger.warning(
                "transformers not available, using keyword fallback only. "
                "Install with: pip install transformers torch"
            )
            return
        
        try:
            logger.info(f"Loading emotion model: {self.model_name}")
            self.classifier = pipeline(
                "text-classification",
                model=self.model_name,
                return_all_scores=True,
                device=-1  # CPU (-1), use 0 for GPU
            )
            logger.info("Transformer emotion detector loaded successfully")
        except Exception as e:
            logger.error(
                f"Failed to load emotion model: {e}. Using keyword fallback.",
                exc_info=True
            )
            self.classifier = None
    
    def detect_emotion(self, text: str) -> str:
        """Detect primary emotion in text.
        
        Args:
            text: Input text
            
        Returns:
            Primary emotion label
        """
        prediction = self.detect_emotion_with_confidence(text)
        return prediction.emotion
    
    def detect_emotion_with_confidence(self, text: str) -> EmotionPrediction:
        """Detect emotion with confidence scores.
        
        Args:
            text: Input text
            
        Returns:
            EmotionPrediction with scores
        """
        # Use transformer model if available
        if self.classifier is not None:
            try:
                results = self.classifier(text[:512])[0]  # Truncate to model limit
                
                # Convert to dict for easier access
                scores = {result['label']: result['score'] for result in results}
                
                # Get highest confidence emotion
                primary_emotion = max(scores.items(), key=lambda x: x[1])
                
                logger.debug(
                    "Emotion detected (transformer)",
                    extra={
                        "emotion": primary_emotion[0],
                        "confidence": primary_emotion[1],
                        "text_length": len(text)
                    }
                )
                
                return EmotionPrediction(
                    emotion=primary_emotion[0],
                    confidence=primary_emotion[1],
                    all_scores=scores
                )
                
            except Exception as e:
                logger.error(f"Transformer emotion detection failed: {e}", exc_info=True)
                # Fall through to keyword fallback
        
        # Fallback to keyword-based detection
        emotion = self.fallback_detector.detect_emotion(text)
        
        logger.debug(
            "Emotion detected (keyword fallback)",
            extra={"emotion": emotion, "text_length": len(text)}
        )
        
        return EmotionPrediction(
            emotion=emotion,
            confidence=0.6,  # Fixed confidence for keyword detection
            all_scores={emotion: 0.6}
        )
    
    def get_emotion_weights(self, emotion: str) -> float:
        """Get importance weight for an emotion.
        
        Args:
            emotion: Emotion label
            
        Returns:
            Importance weight (0.0-1.0)
        """
        return self.EMOTION_WEIGHTS.get(emotion, 0.5)
    
    def calculate_importance_score(self, text: str, emotion: str) -> float:
        """Calculate importance score for a message.
        
        Combines emotion weight with text characteristics.
        
        Args:
            text: Message text
            emotion: Detected emotion
            
        Returns:
            Importance score (0.0-1.0)
        """
        base_weight = self.get_emotion_weights(emotion)
        
        # Text length factor (longer = slightly more important)
        length_factor = min(len(text) / 500, 1.2)
        
        # Question factor (questions often important)
        question_factor = 1.1 if "?" in text else 1.0
        
        # Combine factors
        importance = min(base_weight * length_factor * question_factor, 1.0)
        
        return importance
    
    def get_multi_label_emotions(
        self,
        text: str,
        threshold: float = None
    ) -> List[Tuple[str, float]]:
        """Get all emotions above confidence threshold.
        
        Args:
            text: Input text
            threshold: Confidence threshold (default from settings)
            
        Returns:
            List of (emotion, confidence) tuples
        """
        threshold = threshold or self.threshold
        prediction = self.detect_emotion_with_confidence(text)
        
        # Filter emotions above threshold
        multi_labels = [
            (emotion, score)
            for emotion, score in prediction.all_scores.items()
            if score >= threshold
        ]
        
        # Sort by confidence descending
        multi_labels.sort(key=lambda x: x[1], reverse=True)
        
        return multi_labels
