# 🎙️ Realtime Voice Pipeline - Low-Latency TTS/STT System

A production-ready realtime voice processing pipeline with ElevenLabs TTS, Whisper STT, and intelligent caching. Achieves <350ms average round-trip latency with 80%+ cache hit rate in repeated calls.

[![CI](https://github.com/mjabubakar/realtime-voice-pipeline/workflows/CI%20Pipeline/badge.svg)](https://github.com/mjabubakar/realtime-voice-pipeline/actions)
[![codecov](https://codecov.io/github/mjabubakar/realtime-voice-pipeline/graph/badge.svg?token=588QZYSIQG)](https://codecov.io/github/mjabubakar/realtime-voice-pipeline)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 🚀 Features

- **Low Latency**: <300ms average round-trip time for TTS
- **Dual Pipeline**:
  - **TTS**: Text → Speech (ElevenLabs WebSocket API)
  - **STT**: Speech → Text (Whisper/faster-whisper)
- **Intelligent Caching**: Redis-based deduplication, 80%+ reduction in repeated TTS calls
- **WebSocket Streaming**: Real-time bidirectional communication
- **Sentiment Analysis**: Live transcript analysis with TextBlob
- **Audio Normalization**: PyDub-powered audio processing for consistency
- **Resilient Architecture**: Circuit breaker pattern, automatic retries with exponential backoff
- **Concurrent Support**: 50+ concurrent WebSocket streams
- **Production Ready**: Docker, CI, health checks
- **High Test Coverage**: 85%+ test coverage with pytest

## 📋 Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ WebSocket (Bidirectional)
       ▼
┌─────────────────────────────────┐
│     FastAPI WebSocket Server     │
│  ┌──────────────────────────┐   │
│  │  Circuit Breaker Layer   │   │
│  └───────────┬──────────────┘   │
│              ▼                   │
│  ┌──────────────────────────┐   │
│  │    Message Router        │   │
│  │  - type: "text" → TTS    │   │
│  │  - type: "audio" → STT   │   │ ← STT service used here
│  └────┬────────────────┬────┘   │
│       │                │         │
│   TTS Flow         STT Flow      │
│       ▼                ▼         │
│  ┌─────────┐    ┌──────────┐   │
│  │ Cache   │    │ Whisper  │   │
│  │ Redis   │    │   STT    │   │
│  └────┬────┘    └────┬─────┘   │
│       │              │          │
│       ▼              ▼          │
│  ┌──────────┐  ┌──────────┐   │
│  │ElevenLabs│  │Sentiment │   │
│  │   TTS    │  │ Analysis │   │
│  └────┬─────┘  └────┬─────┘   │
│       ▼              ▼          │
│  ┌──────────────────────────┐  │
│  │   Audio Processor        │  │
│  └──────────┬───────────────┘  │
└─────────────┼──────────────────┘
              ▼
       ┌─────────────┐
       │   Response  │
       └─────────────┘
```

## 🛠️ Tech Stack

- **Backend**: FastAPI + Uvicorn (ASGI)
- **TTS**: ElevenLabs WebSocket API
- **STT**: faster-whisper (local Whisper)
- **Cache**: Redis 8.x
- **Audio Processing**: PyDub + FFmpeg
- **Sentiment Analysis**: TextBlob
- **Resilience**: Tenacity (retries) + Circuit Breaker
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **CI**: GitHub Actions
- **Deployment**: Docker, Render.com
- **Monitoring**: Health checks, metrics endpoints

## 📦 Installation

### Prerequisites

- Python 3.13+
- Redis 8.x
- FFmpeg
- ElevenLabs API key

### Quick Start

```bash
# Clone repository
git clone https://github.com/mjabubakar/realtime-voice-pipeline.git
cd realtime-voice-pipeline

# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Setup pre-commit hooks (optional but recommended)
poetry run pre-commit install

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
# Required: ELEVENLABS_API_KEY
nano .env  # or use your preferred editor

# Activate Poetry shell (optional - creates a virtual environment)
poetry env activate

# Start Redis (required)
docker run -d -p 6379:6379 redis:8-alpine

# Run the application
poetry run uvicorn app.main:app --reload

# Or if in poetry shell:
uvicorn app.main:app --reload
```

### Environment Variables

```bash
# Required
ELEVENLABS_API_KEY=your_api_key_here

# Optional (defaults provided)
ELEVENLABS_VOICE_ID="IKne3meq5aSn9XLyUdCD"
ELEVENLABS_MODEL_ID="eleven_monolingual_v1"
WHISPER_MODEL_SIZE="base"
WHISPER_DEVICE="cpu"
WHISPER_COMPUTE_TYPE="int8"
REDIS_HOST="localhost"
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=""
REDIS_CACHE_TTL=3600
AUDIO_SAMPLE_RATE=22050
AUDIO_CHANNELS=1
AUDIO_FORMAT="mp3"
TARGET_DBFS=-20.0
MAX_RETRIES=3
RETRY_MULTIPLIER=2.0
RETRY_MIN_WAIT=1.0
RETRY_MAX_WAIT=10.0
LOG_LEVEL="INFO"
LOG_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

## 🏃 Running

### Local Development

```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Run application
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Access playground at http://localhost:8000
```

### Docker Compose

```bash
# Build and start all services
docker compose up --build

# Run in background
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### Production

```bash
# Run with multiple workers
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Or use Gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov-report=html  --cov-branch

# Check coverage threshold (85%+)
coverage report --fail-under=85

# Run specific test file
pytest tests/test_cache.py -v

# Run load tests
locust -f tests/load_test.py --headless -u 50 -r 5 -t 60s --host http://localhost:8000
```

## 🔌 API Reference

See **[docs/api.md](docs/api.md)** for full WebSocket and REST endpoint documentation.

## 🏗️ Architecture Reference

See **[docs/architecture.md](docs/architecture.md)** for an overview of the system architecture.

## 🎯 Key Achievements

### ✅ Performance

- ✓ <350ms average latency (target: <350ms)
- ✓ 50+ concurrent streams (target: 50+)
- ✓ Cache reduction in repeated calls: ≥80%

### ✅ Reliability

- ✓ 85%+ test coverage (target: 85%+)
- ✓ Circuit breaker pattern implemented
- ✓ Automatic retries with exponential backoff
- ✓ Graceful error handling

### ✅ Production Ready

- ✓ Docker containerization
- ✓ CI with GitHub Actions
- ✓ Deployed to Render.com
- ✓ Health checks and monitoring
- ✓ Comprehensive logging

## 📁 Project Structure

```
realtime-voice-pipeline/
│
├── 📄 pyproject.toml # Poetry configuration & dependencies
├── 📄 README.md # Main documentation
├── 📄 .env.example # Environment template
├── 📄 .gitignore # Git ignore rules
├── 📄 .pre-commit-config.yaml # Pre-commit hooks
├── 📄 Makefile # Build & run commands
│
├── 🐳 Docker/Deployment
│ ├── Dockerfile # Docker image definition
│ ├── docker-compose.yml # Multi-container setup
│ └── .dockerignore # Docker ignore rules
│
├── 🚀 app/ # Main application directory
│ ├── main.py # FastAPI app with WebSocket endpoint
│ ├── config.py # Application settings (Pydantic)
│ │
│ ├── services/ # Business logic services
│ │ ├── **init**.py
│ │ ├── tts_service.py # ElevenLabs TTS (WebSocket + REST)
│ │ ├── stt_service.py # Whisper STT (faster-whisper)
│ │ ├── cache_service.py # Redis caching & deduplication
│ │ ├── sentiment_service.py # TextBlob sentiment analysis
│ │ └── audio_processor.py # PyDub audio processing
│ │
│ ├── utils/ # Utility modules
│ │ ├── **init**.py
│ │ └── circuit_breaker.py # Circuit breaker pattern
│ │
│ ├── templates/ # Jinja2 HTML templates
│ │ └── index.html # Main playground UI
│ │
│ └── static/ # CSS, JS assets
│ ├── css/
│ │ └── style.css # Main stylesheet
│ └── js/
│ └── main.js # WebSocket client logic
│
├── 🧪 tests/ # Test suite (85%+ coverage)
│ ├── **init**.py
│ ├── conftest.py # Pytest fixtures
│ ├── test_suite.py # Main tests
│ ├── test_main.py # FastAPI endpoint tests
│ ├── test_integration.py # End-to-end tests
│ └── load_test.py # Locust load testing
│ └── test_cache_service.py # Cache service tests
│ └── test_tts_service.py # TTS service tests
│ └── test_stt_service.py # STT service tests
│ └── test_sentiment_service.py # Sentiment analysis tests
│ └── test_audio_processor.py # Audio processing tests
│ └── test_circuit_breaker.py # Circuit breaker tests
│
├── 📊 .github/ # CI/CD pipelines
│ └── workflows/
│ └── ci.yml # CI pipeline
│
└── 📚 docs/ # Additional documentation
├── architecture.md # System architecture
└── api.md # API documentation
```

## 🚀 Deployment

### Render.com (One-Click Deploy)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

Or manually:

1. Fork this repository
2. Create new Web Service on Render
3. Connect GitHub repository
4. Add environment variables:
   - `ELEVENLABS_API_KEY`
5. Deploy!

### Docker Hub

```bash
# Pull image
docker pull yourusername/realtime-voice-pipeline:latest

# Run container
docker run -d \
  -p 8000:8000 \
  -e ELEVENLABS_API_KEY=your_key \
  -e REDIS_HOST=your_redis_host \
  yourusername/realtime-voice-pipeline:latest
```

## 📈 Monitoring

### Metrics Available

- Active WebSocket connections
- Cache hit/miss rates
- Request latency (avg, median, p95, p99)
- Circuit breaker status
- Redis connection health
- Error rates

### Logging

Logs are structured and include:

- Request/response timing
- Cache operations
- Service health
- Error traces

```bash
# View logs
docker compose logs -f app

# Filter specific service
docker compose logs -f redis
```
