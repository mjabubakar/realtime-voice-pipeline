import logging
from typing import Dict

from textblob import TextBlob

logger = logging.getLogger(__name__)


class SentimentService:
    """Sentiment analysis for transcripts using TextBlob"""

    def __init__(self):
        """Initialize sentiment analyzer"""
        logger.info("Sentiment analyzer initialized")

    def analyze(self, text: str) -> Dict:
        """
        Analyze sentiment of text

        Args:
            text: Input text to analyze

        Returns:
            Dict with sentiment scores
        """
        try:
            blob = TextBlob(text)

            # Get polarity (-1 to 1) and subjectivity (0 to 1)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity

            # Classify sentiment
            if polarity > 0.1:
                label = "positive"
            elif polarity < -0.1:
                label = "negative"
            else:
                label = "neutral"

            result = {
                "polarity": round(polarity, 3),
                "subjectivity": round(subjectivity, 3),
                "label": label,
            }

            logger.debug(f"Sentiment analysis: {text[:30]}... -> {label} ({polarity:.2f})")

            return result

        except Exception as e:
            logger.error(f"Sentiment analysis error: {str(e)}")
            return {"polarity": 0.0, "subjectivity": 0.0, "label": "unknown"}

    def analyze_batch(self, texts: list) -> list:
        """
        Analyze sentiment for multiple texts

        Args:
            texts: List of texts to analyze

        Returns:
            List of sentiment results
        """
        return [self.analyze(text) for text in texts]

    def get_emotion(self, text: str) -> str:
        """
        Get basic emotion from text

        Args:
            text: Input text

        Returns:
            Emotion label
        """
        sentiment = self.analyze(text)
        polarity = sentiment["polarity"]
        subjectivity = sentiment["subjectivity"]

        # Map to emotions
        if polarity > 0.5:
            return "joy" if subjectivity > 0.5 else "satisfaction"
        elif polarity > 0.1:
            return "content"
        elif polarity < -0.5:
            return "anger" if subjectivity > 0.5 else "sadness"
        elif polarity < -0.1:
            return "disappointment"
        else:
            return "neutral"

    def extract_keywords(self, text: str, top_n: int = 5) -> list:
        """
        Extract key noun phrases from text

        Args:
            text: Input text
            top_n: Number of phrases to return

        Returns:
            List of noun phrases
        """
        try:
            blob = TextBlob(text)
            phrases = blob.noun_phrases

            # Count frequency
            from collections import Counter

            phrase_counts = Counter(phrases)

            # Get top phrases
            top_phrases = [phrase for phrase, _ in phrase_counts.most_common(top_n)]

            return top_phrases

        except Exception as e:
            logger.error(f"Keyword extraction error: {str(e)}")
            return []
