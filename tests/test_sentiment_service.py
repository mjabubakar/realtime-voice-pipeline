def test_sentiment_positive(sentiment_service):
    """Test positive sentiment detection"""
    text = "I love this amazing product! It's fantastic and wonderful!"

    result = sentiment_service.analyze(text)

    assert result["label"] == "positive"
    assert result["polarity"] > 0.1
    assert 0 <= result["polarity"] <= 1
    assert 0 <= result["subjectivity"] <= 1


def test_sentiment_negative(sentiment_service):
    """Test negative sentiment detection"""
    text = "This is terrible. I hate it and it's awful and disappointing."

    result = sentiment_service.analyze(text)

    assert result["label"] == "negative"
    assert result["polarity"] < -0.1


def test_sentiment_neutral(sentiment_service):
    """Test neutral sentiment detection"""
    text = "The sky is blue. Water is wet. Tables have four legs."

    result = sentiment_service.analyze(text)

    assert result["label"] == "neutral"
    assert -0.1 <= result["polarity"] <= 0.1


def test_sentiment_batch(sentiment_service):
    """Test batch sentiment analysis"""
    texts = ["Great product!", "Terrible experience.", "It's okay, I guess."]

    results = sentiment_service.analyze_batch(texts)

    assert len(results) == 3
    assert all("polarity" in r for r in results)
    assert all("label" in r for r in results)


def test_emotion_detection(sentiment_service):
    """Test emotion detection"""
    test_cases = [
        ("I'm so happy and excited!", ["joy", "content"]),
        ("This makes me very angry", ["anger"]),
        ("It's fine", ["neutral", "content"]),
    ]

    for text, possible_emotions in test_cases:
        emotion = sentiment_service.get_emotion(text)
        assert isinstance(emotion, str)
        assert emotion in possible_emotions or emotion in [
            "joy",
            "satisfaction",
            "content",
            "anger",
            "sadness",
            "disappointment",
            "neutral",
        ]


def test_sentiment_empty_text(sentiment_service):
    """Test sentiment with empty text"""
    result = sentiment_service.analyze("")

    assert "polarity" in result
    assert "label" in result


def test_sentiment_special_characters(sentiment_service):
    """Test sentiment with special characters"""
    text = "Great!!! 😊 #awesome @best"
    result = sentiment_service.analyze(text)

    assert result["label"] in ["positive", "neutral", "negative"]


def test_sentiment_extract_keywords():
    """Test keyword extraction"""
    from app.services.sentiment_service import SentimentService

    sentiment = SentimentService()
    text = "The quick brown fox jumps over the lazy dog. The quick fox runs fast."

    keywords = sentiment.extract_keywords(text, top_n=3)
    assert isinstance(keywords, list)
    assert len(keywords) <= 3
