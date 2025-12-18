# Whisper Transcription App

High-quality audio and video transcription powered by OpenAI Whisper Large-V3 via faster-whisper, with speaker diarization and multiple export formats.

## Features

- **File Upload**: Drag & drop or browse to upload audio/video files
- **YouTube Support**: Paste a YouTube URL to transcribe video content
- **High Accuracy**: Uses Whisper Large-V3 model with quality-focused settings
- **Speaker Recognition**: Automatic speaker diarization using pyannote-audio
- **Language Support**: English, French, or auto-detection
- **Multiple Export Formats**: TXT, Markdown, SRT, PDF, DOCX
- **Timestamps**: View transcription with precise timestamps
- **Apple Silicon Optimized**: Configured for best performance on M1/M2/M3 Macs

## Architecture

- **Frontend**: React 18 with Tailwind CSS
- **Backend**: FastAPI (Python) with faster-whisper
- **Transcription**: OpenAI Whisper Large-V3 via CTranslate2
- **Speaker Diarization**: pyannote-audio 3.1

## Quick Start

### Prerequisites

1. **ffmpeg** (required for audio extraction)
   ```bash
   # macOS
   brew install ffmpeg
   ```

2. **HuggingFace Token** (required for speaker diarization)
   - Get your token at: https://huggingface.co/settings/tokens
   - Accept the model terms at: https://huggingface.co/pyannote/speaker-diarization-3.1

### Setup

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set your HuggingFace token for speaker diarization
export HF_TOKEN="your_huggingface_token"

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

### Using Docker Compose

```bash
# Set your HuggingFace token
export HF_TOKEN="your_huggingface_token"

# Start both services
docker-compose up --build
```

Access at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## Configuration

### Backend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_TOKEN` | - | HuggingFace token for speaker diarization (required) |
| `WHISPER_MODEL_SIZE` | `large-v3` | Model size (`tiny`, `base`, `small`, `medium`, `large-v3`) |

The backend automatically detects Apple Silicon and configures optimal settings.

### Frontend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REACT_APP_API_URL` | `http://localhost:8000` | Backend API URL |

## API Endpoints

### `POST /transcribe/file`
Upload and transcribe an audio/video file.

**Query Parameters:**
- `language`: Language code (`en`, `fr`, or `auto`)
- `enable_diarization`: Enable speaker identification (default: true)

### `POST /transcribe/youtube`
Download and transcribe audio from a YouTube URL.

**Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "language": "auto",
  "enable_diarization": true
}
```

### `GET /job/{job_id}`
Get transcription status and results.

### `GET /job/{job_id}/export?format=txt`
Export transcript in specified format: `txt`, `md`, `srt`, `pdf`, `docx`

## Export Formats

| Format | Description |
|--------|-------------|
| TXT | Plain text with timestamps and speakers |
| Markdown | Formatted markdown with headers per speaker |
| SRT | Subtitle format for video players |
| PDF | Formatted PDF document |
| DOCX | Microsoft Word document |

## Performance on Apple Silicon

On MacBook Air M3 with 24GB RAM:
- **Whisper**: Runs on CPU with float32 for best quality
- **Diarization**: Runs on MPS (Metal) for GPU acceleration
- **Processing**: Expect ~0.5-1x real-time for transcription

## Supported Languages

- English (`en`)
- French (`fr`)
- Auto-detect (`auto`)

## License

MIT
