# 📡 API Reference

Complete API documentation for Realtime Voice Pipeline.

**Base URL:** `http://localhost:8000` (development) or `https://realtime-voice-pipeline.onrender.com` (production)

---

## Table of Contents

- [WebSocket API](#websocket-api)
- [REST API](#rest-api)
- [Error Handling](#error-handling)
- [Rate Limits](#rate-limits)
- [Examples](#examples)

---

## WebSocket API

### Connect to WebSocket

**Endpoint:** `WS /ws/voice`

**Connection:**

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/voice");

ws.onopen = () => {
  console.log("Connected");
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Received:", data);
};

ws.onerror = (error) => {
  console.error("Error:", error);
};

ws.onclose = () => {
  console.log("Disconnected");
};
```

---

### Text-to-Speech (TTS)

**Send Message:**

```json
{
  "type": "text",
  "text": "Hello, world! This text will be converted to speech."
}
```

**Receive Response:**

```json
{
  "type": "audio",
  "audio": "base64_encoded_audio_data_here...",
  "duration": 2.5,
  "latency_ms": 342,
  "cached": false,
  "sentiment": {
    "polarity": 0.5,
    "subjectivity": 0.6,
    "label": "positive"
  }
}
```

**Response Fields:**

| Field                    | Type    | Description                          |
| ------------------------ | ------- | ------------------------------------ |
| `type`                   | string  | Always "audio" for TTS response      |
| `audio`                  | string  | Base64-encoded audio data (MP3)      |
| `duration`               | float   | Audio duration in seconds            |
| `latency_ms`             | integer | Round-trip latency in milliseconds   |
| `cached`                 | boolean | Whether audio was served from cache  |
| `sentiment`              | object  | Sentiment analysis of input text     |
| `sentiment.polarity`     | float   | -1 (negative) to 1 (positive)        |
| `sentiment.subjectivity` | float   | 0 (objective) to 1 (subjective)      |
| `sentiment.label`        | string  | "positive", "negative", or "neutral" |

**Example:**

```javascript
ws.send(
  JSON.stringify({
    type: "text",
    text: "Convert this to speech",
  })
);
```

---

### Speech-to-Text (STT)

**Send Message:**

```json
{
  "type": "audio",
  "audio": "base64_encoded_audio_data...",
  "language": "en"
}
```

**Request Fields:**

| Field      | Type   | Required | Description                               |
| ---------- | ------ | -------- | ----------------------------------------- |
| `type`     | string | Yes      | Must be "audio"                           |
| `audio`    | string | Yes      | Base64-encoded audio (WAV, MP3, etc.)     |
| `language` | string | No       | Language code (e.g., "en", "es") for hint |

**Receive Response:**

```json
{
  "type": "transcript",
  "text": "This is the transcribed text from your audio",
  "language": "en",
  "language_probability": 0.95,
  "duration": 3.2,
  "latency_ms": 850,
  "segments": [
    {
      "start": 0.0,
      "end": 3.2,
      "text": "This is the transcribed text from your audio",
      "avg_logprob": -0.3,
      "no_speech_prob": 0.1
    }
  ],
  "sentiment": {
    "polarity": 0.2,
    "subjectivity": 0.4,
    "label": "positive"
  }
}
```

**Response Fields:**

| Field                  | Type    | Description                            |
| ---------------------- | ------- | -------------------------------------- |
| `type`                 | string  | Always "transcript" for STT response   |
| `text`                 | string  | Complete transcribed text              |
| `language`             | string  | Detected language code                 |
| `language_probability` | float   | Confidence of language detection (0-1) |
| `duration`             | float   | Audio duration in seconds              |
| `latency_ms`           | integer | Processing time in milliseconds        |
| `segments`             | array   | Timestamped transcript segments        |
| `sentiment`            | object  | Sentiment analysis of transcript       |

---

### Error Response

**Format:**

```json
{
  "type": "error",
  "message": "Descriptive error message"
}
```

**Common Errors:**

- "Empty text" - Text field is empty
- "Empty audio data" - Audio field is empty
- "Invalid message type" - Unknown message type
- "TTS service error: ..." - TTS generation failed
- "STT service error: ..." - Transcription failed

---

## REST API

### POST /api/tts

Convert text to speech via REST API.

**Request:**

```http
POST /api/tts HTTP/1.1
Content-Type: application/json

{
  "text": "Hello, world!",
  "use_cache": true
}
```

**Request Body:**

| Field       | Type    | Required | Default | Description               |
| ----------- | ------- | -------- | ------- | ------------------------- |
| `text`      | string  | Yes      | -       | Text to convert to speech |
| `use_cache` | boolean | No       | true    | Whether to use cache      |

**Response (200 OK):**

```json
{
  "audio_base64": "base64_encoded_audio...",
  "cached": false,
  "text": "Hello, world!"
}
```

**Response Fields:**

| Field          | Type    | Description                |
| -------------- | ------- | -------------------------- |
| `audio_base64` | string  | Base64-encoded audio (MP3) |
| `cached`       | boolean | Whether served from cache  |
| `text`         | string  | Original input text        |

**Error Response (400 Bad Request):**

```json
{
  "detail": "Text is required"
}
```

**Error Response (500 Internal Server Error):**

```json
{
  "detail": "TTS service unavailable"
}
```

---

### POST /api/stt

Convert speech to text via REST API.

**Request:**

```http
POST /api/stt HTTP/1.1
Content-Type: application/json

{
  "audio_base64": "base64_encoded_audio...",
  "language": "en"
}
```

**Request Body:**

| Field          | Type   | Required | Default | Description                      |
| -------------- | ------ | -------- | ------- | -------------------------------- |
| `audio_base64` | string | Yes      | -       | Base64-encoded audio             |
| `language`     | string | No       | null    | Language hint (e.g., "en", "es") |

**Response (200 OK):**

```json
{
  "text": "This is the transcribed text",
  "language": "en",
  "language_probability": 0.95,
  "duration": 2.5,
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "This is the transcribed text",
      "avg_logprob": -0.3,
      "no_speech_prob": 0.1
    }
  ],
  "sentiment": {
    "polarity": 0.3,
    "subjectivity": 0.5,
    "label": "positive"
  }
}
```

**Error Response (400 Bad Request):**

```json
{
  "detail": "Audio data is required"
}
```

---

### GET /health

Check service health status.

**Request:**

```http
GET /health HTTP/1.1
```

**Response (200 OK):**

```json
{
  "status": "healthy",
  "timestamp": "2024-11-21T10:30:00.123Z",
  "active_connections": 12,
  "services": {
    "cache": true,
    "tts": "closed"
  }
}
```

**Response Fields:**

| Field                | Type    | Description                                          |
| -------------------- | ------- | ---------------------------------------------------- |
| `status`             | string  | Overall health: "healthy" or "unhealthy"             |
| `timestamp`          | string  | ISO 8601 timestamp                                   |
| `active_connections` | integer | Number of active WebSocket connections               |
| `services.cache`     | boolean | Redis connectivity status                            |
| `services.tts`       | string  | Circuit breaker state: "closed", "open", "half_open" |

**cURL Example:**

```bash
curl http://localhost:8000/health
```

---

### GET /stats

Get system statistics and metrics.

**Request:**

```http
GET /stats HTTP/1.1
```

**Response (200 OK):**

```json
{
  "active_connections": 12,
  "cache_stats": {
    "hits": 620,
    "misses": 380,
    "total_requests": 1000,
    "hit_rate": 62.0,
    "reduction_percentage": 62.0,
    "redis_connected": true,
    "total_connections": 50,
    "total_commands": 2000
  },
  "circuit_breaker": {
    "state": "closed",
    "failures": 0
  }
}
```

**Response Fields:**

| Field                              | Type    | Description                      |
| ---------------------------------- | ------- | -------------------------------- |
| `active_connections`               | integer | Current WebSocket connections    |
| `cache_stats.hits`                 | integer | Number of cache hits             |
| `cache_stats.misses`               | integer | Number of cache misses           |
| `cache_stats.hit_rate`             | float   | Cache hit rate percentage        |
| `cache_stats.reduction_percentage` | float   | API call reduction               |
| `circuit_breaker.state`            | string  | "closed", "open", or "half_open" |
| `circuit_breaker.failures`         | integer | Consecutive failure count        |

**cURL Example:**

```bash
curl http://localhost:8000/stats
```

---

### GET /

Interactive web playground.

**Request:**

```http
GET / HTTP/1.1
```

**Response:** HTML page with interactive UI for testing TTS and STT.

**Features:**

- Text-to-Speech tab
- Speech-to-Text tab
- Real-time metrics
- WebSocket connection status
- Log console

---

## Error Handling

### HTTP Status Codes

| Code | Meaning               | When                                 |
| ---- | --------------------- | ------------------------------------ |
| 200  | OK                    | Request successful                   |
| 400  | Bad Request           | Invalid input (missing/empty fields) |
| 500  | Internal Server Error | Service failure                      |
| 503  | Service Unavailable   | Circuit breaker open                 |

### WebSocket Errors

**Connection Errors:**

- Connection refused: Server not running
- Handshake failed: CORS or auth issue
- Unexpected disconnect: Network issue

**Message Errors:**
All errors returned as:

```json
{
  "type": "error",
  "message": "..."
}
```

---

## Rate Limits

### Current Limits

- **WebSocket connections:** 50+ concurrent (tested)
- **REST API:** No explicit limit (depends on ElevenLabs)
- **ElevenLabs TTS:** Check your plan limits
- **Cache TTL:** 1 hour per entry

### Recommendations

- Use caching (`use_cache: true`) to reduce API calls
- Reuse WebSocket connections
- Monitor `/stats` for usage patterns

---

## Best Practices

### Performance

- ✅ Use WebSocket for real-time applications
- ✅ Enable caching (`use_cache: true`)
- ✅ Reuse connections
- ✅ Monitor `/stats` regularly

### Error Handling

- ✅ Implement exponential backoff for retries
- ✅ Handle all error types gracefully
- ✅ Log errors for debugging
- ✅ Provide user feedback

### Security

- ✅ Use HTTPS/WSS in production
- ✅ Validate input sizes (text length, audio size)
- ✅ Implement rate limiting if needed
- ✅ Sanitize user input

### Testing

- ✅ Test with various audio formats
- ✅ Test with different languages
- ✅ Test error scenarios
- ✅ Load test before production

---

## Support

For questions:

- 📚 Documentation: See [README.md](../README.md) and [architecture.md](architecture.md)
