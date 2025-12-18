# Whisper Transcription App

High-quality audio and video transcription powered by OpenAI Whisper Large-V3 via faster-whisper.

## Features

- **File Upload**: Drag & drop or browse to upload audio/video files
- **YouTube Support**: Paste a YouTube URL to transcribe video content
- **High Accuracy**: Uses Whisper Large-V3 model for state-of-the-art transcription
- **Timestamps**: View transcription with precise timestamps
- **Export**: Copy to clipboard or download as SRT subtitle file
- **Language Detection**: Automatic language detection with confidence score
- **Multiple Formats**: Supports MP3, WAV, MP4, MKV, AVI, WebM, M4A, FLAC, OGG, and more

## Architecture

- **Frontend**: React 18 with Tailwind CSS
- **Backend**: FastAPI (Python) with faster-whisper
- **Transcription Engine**: OpenAI Whisper Large-V3 via CTranslate2

## Quick Start

### Using Docker Compose (Recommended)

```bash
docker-compose up --build
```

This will start:
- Backend API at http://localhost:8000
- Frontend at http://localhost:3000

### Manual Setup

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install ffmpeg (required for audio extraction)
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
# Windows: Download from https://ffmpeg.org/download.html

# Run the server
uvicorn main:app --host 0.0.0.0 --port 8000
```

#### Frontend

```bash
# Install dependencies
npm install

# Start development server
npm start
```

## Configuration

### Backend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_DEVICE` | `cpu` | Device to run model on (`cpu` or `cuda`) |
| `WHISPER_COMPUTE_TYPE` | `int8` | Compute precision (`int8`, `float16`, `float32`) |
| `WHISPER_MODEL_SIZE` | `large-v3` | Model size (`tiny`, `base`, `small`, `medium`, `large-v3`) |

### Frontend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REACT_APP_API_URL` | `http://localhost:8000` | Backend API URL |

## API Endpoints

### `POST /transcribe/file`
Upload and transcribe an audio/video file.

**Parameters:**
- `file`: The audio/video file (multipart form data)
- `beam_size`: Beam search size (default: 5)
- `patience`: Beam search patience (default: 1.0)
- `vad_filter`: Enable voice activity detection (default: true)
- `word_timestamps`: Include word-level timestamps (default: true)

**Response:**
```json
{
  "job_id": "uuid",
  "status": "processing"
}
```

### `POST /transcribe/youtube`
Download and transcribe audio from a YouTube URL.

**Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=..."
}
```

### `GET /job/{job_id}`
Get the status and result of a transcription job.

**Response (completed):**
```json
{
  "job_id": "uuid",
  "status": "completed",
  "progress": 100,
  "result": "Full transcription text...",
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "Hello world"
    }
  ],
  "language": "en",
  "language_probability": 0.99
}
```

## Performance Notes

- **CPU**: Using INT8 quantization for reasonable performance
- **GPU**: For faster transcription, set `WHISPER_DEVICE=cuda` and `WHISPER_COMPUTE_TYPE=float16`
- **Model Loading**: First run downloads the model (~3GB for large-v3)
- **Processing Time**: Expect ~1x real-time on modern CPU, ~4x faster on GPU

## License

MIT
