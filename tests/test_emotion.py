"""Test suite for emotion tracking."""

import pytest
from app.services.emotion_tracker import EmotionTracker


@pytest.fixture
def emotion_tracker():
    """Create emotion tracker instance."""
    return EmotionTracker()


def test_detect_joy(emotion_tracker):
    """Test joy detection."""
    text = "I'm so happy and excited about this!"
    state = emotion_tracker.detect_emotion(text)
    
    assert state.emotion == "joy"
    assert state.confidence > 0.5


def test_detect_sadness(emotion_tracker):
    """Test sadness detection."""
    text = "I'm feeling really sad and hurt today"
    state = emotion_tracker.detect_emotion(text)
    
    assert state.emotion == "sadness"
    assert state.confidence > 0.5


def test_detect_anger(emotion_tracker):
    """Test anger detection."""
    text = "I'm so angry and frustrated with this situation!"
    state = emotion_tracker.detect_emotion(text)
    
    assert state.emotion == "anger"
    assert state.confidence > 0.5


def test_detect_neutral(emotion_tracker):
    """Test neutral detection."""
    text = "The weather is cloudy today"
    state = emotion_tracker.detect_emotion(text)
    
    assert state.emotion == "neutral"


def test_importance_scoring(emotion_tracker):
    """Test importance score calculation."""
    # High importance: emotional, long, with questions
    high_importance_text = "I'm really worried about this situation. What should I do? I've been thinking about this all day and I need advice."
    state_high = emotion_tracker.detect_emotion(high_importance_text)
    
    # Low importance: short, neutral
    low_importance_text = "Ok"
    state_low = emotion_tracker.detect_emotion(low_importance_text)
    
    assert state_high.importance_score > state_low.importance_score


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
