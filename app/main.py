import asyncio
import base64
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.services.audio_processor import AudioProcessor
from app.services.cache_service import CacheService
from app.services.sentiment_service import SentimentService
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.utils.circuit_breaker import CircuitBreaker

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Starting Realtime Voice Pipeline API...")
    await cache_service.connect()
    logger.info("Services initialized successfully")

    yield  # App runs here

    # --- Shutdown ---
    logger.info("Shutting down Realtime Voice Pipeline API...")
    await cache_service.disconnect()
    await tts_service.close()
    logger.info("Shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    lifespan=lifespan,
    title="Realtime Voice Pipeline API",
    description="Low-latency voice processing with TTS/STT",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup static files and templates
BASE_DIR = Path(__file__).resolve().parent

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Initialize services
tts_service = TTSService()
stt_service = STTService()
cache_service = CacheService()
sentiment_service = SentimentService()
audio_processor = AudioProcessor()

# Circuit breaker for TTS service
tts_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout_duration=60, name="TTS Service")

# Track active connections
active_connections = set()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint with API playground"""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_connections": len(active_connections),
        "services": {
            "cache": await cache_service.ping(),
            "tts": tts_circuit_breaker.state,
        },
    }


@app.get("/stats")
async def get_stats():
    """Get pipeline statistics"""
    cache_stats = await cache_service.get_stats()
    return {
        "active_connections": len(active_connections),
        "cache_stats": cache_stats,
        "circuit_breaker": {
            "state": tts_circuit_breaker.state.value,
            "failures": tts_circuit_breaker.failure_count,
        },
    }


@app.post("/api/tts")
async def text_to_speech_endpoint(request: dict):
    """
    REST endpoint for Text-to-Speech

    Request body:
    {
        "text": "Text to convert to speech",
        "use_cache": true
    }
    """
    text = request.get("text", "").strip()
    use_cache = request.get("use_cache", True)

    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    # Check cache if enabled
    if use_cache:
        cached_audio = await cache_service.get(text)
        if cached_audio:
            return {"audio_base64": cached_audio.decode("latin1"), "cached": True, "text": text}

    # Generate audio
    try:
        audio_data = await tts_circuit_breaker.call(tts_service.text_to_speech(text))

        # Cache if enabled
        if use_cache:
            await cache_service.set(text, audio_data)

        # Normalize
        normalized = audio_processor.normalize(audio_data)

        return {"audio_base64": normalized.decode("latin1"), "cached": False, "text": text}
    except Exception as e:
        logger.error(f"TTS API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stt")
async def speech_to_text_endpoint(request: dict):
    """
    REST endpoint for Speech-to-Text

    Request body:
    {
        "audio_base64": "base64 encoded audio data",
        "language": "en" (optional)
    }
    """
    audio_base64 = request.get("audio_base64", "")
    language = request.get("language")

    if not audio_base64:
        raise HTTPException(status_code=400, detail="Audio data is required")

    try:
        # Decode audio
        audio_bytes = base64.b64decode(audio_base64)

        # Transcribe
        result = await stt_service.transcribe_bytes(audio_bytes, language=language)

        # Analyze sentiment
        sentiment = sentiment_service.analyze(result["text"])

        return {
            "text": result["text"],
            "language": result["language"],
            "language_probability": result["language_probability"],
            "duration": result["duration"],
            "segments": result["segments"],
            "sentiment": sentiment,
        }
    except Exception as e:
        logger.error(f"STT API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/voice")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for realtime voice pipeline
    Handles both text-to-speech (TTS) and speech-to-text (STT)

    Message types:
    - {"type": "text", "text": "..."} → Returns audio (TTS)
    - {"type": "audio", "audio": "base64..."} → Returns transcript (STT)
    """
    await websocket.accept()
    connection_id = id(websocket)
    active_connections.add(connection_id)

    logger.info(f"New WebSocket connection: {connection_id}")

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)

            message_type = message.get("type")

            # ===== TEXT-TO-SPEECH (TTS) FLOW =====
            if message_type == "text":
                text = message.get("text", "").strip()
                if not text:
                    await websocket.send_json({"type": "error", "message": "Empty text"})
                    continue

                logger.info(f"TTS request: {text[:50]}...")

                start_time = asyncio.get_event_loop().time()

                # Check cache first
                cached_audio = await cache_service.get(text)
                if cached_audio:
                    logger.info(f"Cache HIT for text: {text[:30]}...")
                    audio_data = cached_audio
                    from_cache = True
                else:
                    logger.info(f"Cache MISS for text: {text[:30]}...")

                    # Generate speech with circuit breaker
                    try:
                        audio_data = await tts_circuit_breaker.call(
                            tts_service.text_to_speech(text)
                        )

                        # Cache the result
                        await cache_service.set(text, audio_data)
                        from_cache = False

                    except Exception as e:
                        logger.error(f"TTS error: {str(e)}")
                        await websocket.send_json(
                            {"type": "error", "message": f"TTS service error: {str(e)}"}
                        )
                        continue

                # Perform sentiment analysis
                sentiment = sentiment_service.analyze(text)

                # Normalize audio
                normalized_audio = audio_processor.normalize(audio_data)

                # Calculate metrics
                end_time = asyncio.get_event_loop().time()
                latency = int((end_time - start_time) * 1000)

                # Send response
                await websocket.send_json(
                    {
                        "type": "audio",
                        "audio": normalized_audio.decode("latin1"),  # Binary data as string
                        "duration": len(normalized_audio) / 22050,  # Approximate duration
                        "latency_ms": latency,
                        "cached": from_cache,
                        "sentiment": {
                            "polarity": sentiment["polarity"],
                            "subjectivity": sentiment["subjectivity"],
                            "label": sentiment["label"],
                        },
                    }
                )

                logger.info(f"TTS response sent in {latency}ms (cached: {from_cache})")

            # ===== SPEECH-TO-TEXT (STT) FLOW =====
            elif message_type == "audio":
                audio_base64 = message.get("audio", "")
                if not audio_base64:
                    await websocket.send_json({"type": "error", "message": "Empty audio data"})
                    continue

                logger.info(f"STT request: {len(audio_base64)} bytes")

                start_time = asyncio.get_event_loop().time()

                try:
                    # Decode base64 audio
                    import base64

                    audio_bytes = base64.b64decode(audio_base64)

                    # Transcribe audio
                    result = await stt_service.transcribe_bytes(
                        audio_bytes, language=message.get("language")  # Optional language hint
                    )

                    # Perform sentiment analysis on transcript
                    sentiment = sentiment_service.analyze(result["text"])

                    # Calculate metrics
                    end_time = asyncio.get_event_loop().time()
                    latency = int((end_time - start_time) * 1000)

                    # Send response
                    await websocket.send_json(
                        {
                            "type": "transcript",
                            "text": result["text"],
                            "language": result["language"],
                            "language_probability": result["language_probability"],
                            "duration": result["duration"],
                            "segments": result["segments"],
                            "latency_ms": latency,
                            "sentiment": {
                                "polarity": sentiment["polarity"],
                                "subjectivity": sentiment["subjectivity"],
                                "label": sentiment["label"],
                            },
                        }
                    )

                    logger.info(
                        f"STT response sent in {latency}ms: "
                        f"'{result['text'][:50]}...' ({result['language']})"
                    )

                except Exception as e:
                    logger.error(f"STT error: {str(e)}", exc_info=True)
                    await websocket.send_json(
                        {"type": "error", "message": f"STT service error: {str(e)}"}
                    )
                    continue

            # ===== INVALID MESSAGE TYPE =====
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Invalid message type: {message_type}. Expected 'text' or 'audio'",
                    }
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
    finally:
        active_connections.discard(connection_id)
        logger.info(f"Connection closed: {connection_id}. Active: {len(active_connections)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
