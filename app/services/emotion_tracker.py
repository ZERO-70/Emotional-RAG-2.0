"""Emotion detection and importance scoring service."""

import logging
from typing import Tuple, Dict, List
from app.models.memory import EmotionalState

logger = logging.getLogger(__name__)


class EmotionTracker:
    """Tracks emotional states and calculates message importance."""
    
    def __init__(self):
        """Initialize emotion tracker with keyword-based detection."""
        # Phase 1: Rule-based emotion detection
        self.emotion_keywords: Dict[str, List[str]] = {
            'joy': [
                'happy', 'excited', 'love', 'wonderful', 'amazing', 'great',
                'fantastic', 'thrilled', 'delighted', 'cheerful', 'joyful',
                'glad', 'pleased', 'ecstatic', 'elated', '😊', '😄', '❤️', '🥰'
            ],
            'sadness': [
                'sad', 'depressed', 'hurt', 'cry', 'crying', 'tears', 'upset',
                'disappointed', 'heartbroken', 'miserable', 'lonely', 'down',
                'devastated', 'gloomy', 'melancholy', '😢', '😭', '💔'
            ],
            'anger': [
                'angry', 'furious', 'hate', 'annoyed', 'frustrated', 'mad',
                'rage', 'irritated', 'infuriated', 'outraged', 'bitter',
                'resentful', 'hostile', 'aggressive', '😠', '😡', '🤬'
            ],
            'fear': [
                'scared', 'afraid', 'worried', 'anxious', 'terrified', 'panic',
                'nervous', 'frightened', 'alarmed', 'concerned', 'uneasy',
                'apprehensive', 'dread', 'horror', '😰', '😨', '😱'
            ],
            'surprise': [
                'surprised', 'shocked', 'amazed', 'astonished', 'stunned',
                'startled', 'unexpected', 'wow', 'omg', '😮', '😲', '🤯'
            ],
            'disgust': [
                'disgusted', 'gross', 'revolting', 'repulsive', 'nasty',
                'awful', 'terrible', 'horrible', 'sickening', '🤢', '🤮'
            ]
        }
        
        # Weight multipliers for different emotions
        self.emotion_weights = {
            'joy': 0.8,
            'sadness': 1.0,
            'anger': 0.9,
            'fear': 0.95,
            'surprise': 0.7,
            'disgust': 0.75,
            'neutral': 0.5
        }
    
    def detect_emotion(self, text: str) -> EmotionalState:
        """
        Detect emotional state from text using keyword matching.
        
        Args:
            text: Input text to analyze
            
        Returns:
            EmotionalState with emotion label, confidence, and importance score
        """
        text_lower = text.lower()
        
        # Count keyword matches for each emotion
        emotion_scores: Dict[str, int] = {}
        for emotion, keywords in self.emotion_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            emotion_scores[emotion] = score
        
        # Determine dominant emotion
        if not any(emotion_scores.values()):
            emotion = 'neutral'
            confidence = 0.5
        else:
            emotion = max(emotion_scores, key=emotion_scores.get)
            # Normalize confidence (cap at 1.0)
            max_score = emotion_scores[emotion]
            confidence = min(max_score / 3.0, 1.0)
        
        # Calculate importance score
        importance = self.calculate_importance(text, emotion, confidence)
        
        logger.debug(
            f"Emotion detected: {emotion} (confidence={confidence:.2f}, importance={importance:.2f})",
            extra={
                "emotion": emotion,
                "confidence": confidence,
                "importance": importance,
                "text_length": len(text)
            }
        )
        
        return EmotionalState(
            emotion=emotion,
            confidence=confidence,
            importance_score=importance
        )
    
    def calculate_importance(
        self,
        text: str,
        emotion: str,
        emotion_confidence: float
    ) -> float:
        """
        Calculate message importance score (0-1).
        
        Factors:
        - Emotional intensity (weighted by emotion type)
        - Message length (longer = more detailed)
        - Questions (indicates engagement)
        - Exclamations (indicates emphasis)
        - Personal pronouns (indicates personal investment)
        
        Args:
            text: Message content
            emotion: Detected emotion label
            emotion_confidence: Confidence in emotion detection
            
        Returns:
            Importance score between 0.0 and 1.0
        """
        importance = 0.5  # Base score
        
        # Factor 1: Emotional content (weighted)
        if emotion != 'neutral':
            emotion_weight = self.emotion_weights.get(emotion, 0.5)
            importance += emotion_confidence * emotion_weight * 0.3
        
        # Factor 2: Length indicates detail
        text_length = len(text)
        if text_length > 200:
            importance += 0.15
        elif text_length > 100:
            importance += 0.1
        elif text_length < 20:
            importance -= 0.1  # Very short messages less important
        
        # Factor 3: Questions show engagement
        question_count = text.count('?')
        if question_count > 0:
            importance += min(question_count * 0.1, 0.15)
        
        # Factor 4: Exclamations show emphasis
        exclamation_count = text.count('!')
        if exclamation_count > 0:
            importance += min(exclamation_count * 0.05, 0.1)
        
        # Factor 5: Personal pronouns (I, me, my, mine)
        personal_pronouns = ['i ', 'me ', 'my ', 'mine ', "i'm ", "i've ", "i'll "]
        text_lower = ' ' + text.lower() + ' '
        pronoun_count = sum(1 for pronoun in personal_pronouns if pronoun in text_lower)
        if pronoun_count > 0:
            importance += min(pronoun_count * 0.05, 0.1)
        
        # Cap at 1.0
        importance = min(importance, 1.0)
        
        # Floor at 0.1 (even unimportant messages have some value)
        importance = max(importance, 0.1)
        
        return round(importance, 3)
    
    def get_emotional_context_prompt(
        self,
        current_emotion: str,
        current_confidence: float,
        emotional_history: List[str] = None
    ) -> str:
        """
        Generate system prompt addition for emotional awareness.
        
        Args:
            current_emotion: Current detected emotion
            current_confidence: Confidence in current emotion
            emotional_history: Recent emotional moments from memory
            
        Returns:
            Formatted emotional context string
        """
        if current_emotion == 'neutral' or current_confidence < 0.4:
            return ""
        
        context_parts = [
            f"\n## Emotional Context",
            f"User's current emotional state: **{current_emotion}** (confidence: {current_confidence:.0%})"
        ]
        
        # Add response guidance based on emotion
        guidance = {
            'joy': "Respond with enthusiasm and positive reinforcement.",
            'sadness': "Respond with empathy, validation, and gentle support.",
            'anger': "Respond calmly with understanding and de-escalation.",
            'fear': "Respond reassuringly with comfort and practical suggestions.",
            'surprise': "Acknowledge the unexpected nature and provide clarity.",
            'disgust': "Validate their feelings and redirect if appropriate."
        }
        
        if current_emotion in guidance:
            context_parts.append(guidance[current_emotion])
        
        # Add relevant emotional history
        if emotional_history:
            context_parts.append("\n**Relevant past emotional moments:**")
            for moment in emotional_history[:3]:  # Limit to top 3
                context_parts.append(f"- {moment}")
        
        return "\n".join(context_parts)
    
    def boost_score_for_emotion(
        self,
        base_score: float,
        message_emotion: str,
        query_emotion: str
    ) -> float:
        """
        Boost semantic similarity score if emotions match.
        
        Args:
            base_score: Base semantic similarity score
            message_emotion: Emotion of stored message
            query_emotion: Emotion of current query
            
        Returns:
            Boosted score
        """
        if message_emotion == query_emotion and message_emotion != 'neutral':
            # Boost by 20% for matching emotions
            return base_score * 1.2
        return base_score
