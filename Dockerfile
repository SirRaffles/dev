# ==============================================================================
# Whisper Transcription App — Single-container build
# Stage 1: Build React frontend
# Stage 2: Python backend serving API + static frontend
#
# NOTE: MLX/Metal GPU acceleration only works on native macOS (Apple Silicon).
#       In Linux Docker containers, transcription falls back to CPU via faster-whisper.
# ==============================================================================

# --- Stage 1: Frontend build ---
FROM node:20-alpine AS frontend-build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY public/ public/
COPY src/ src/
COPY index.html vite.config.js tsconfig.json tailwind.config.cjs postcss.config.cjs ./
RUN npm run build


# --- Stage 2: Python backend ---
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (ffmpeg for audio processing, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/ .

# Copy frontend build into static/ for serving
COPY --from=frontend-build /app/build ./static/

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser \
    && mkdir -p /app/.cache/huggingface /app/.cache/torch \
    && chown -R appuser:appuser /app

USER appuser

# Environment defaults
ENV HOME=/app
ENV WHISPER_DEVICE=cpu
ENV WHISPER_COMPUTE_TYPE=int8
ENV WHISPER_MODEL_SIZE=large-v3

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
