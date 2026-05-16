# Davrine Transcription App

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

### Advanced Features

- **Audio Restoration**: Built-in noise reduction using noisereduce library for cleaner transcriptions
- **Batch Upload**: Process multiple files simultaneously with batch progress tracking
- **Inline Editor**: Edit transcripts directly with synchronized audio playback
- **Click-to-Seek**: Click timestamps to jump to that position in the audio
- **Speaker Renaming**: Rename detected speakers (e.g., SPEAKER_00 → "John")
- **Search & Replace**: Find and replace text across the entire transcript
- **Auto-Scroll**: Automatically scrolls to follow currently playing audio

## Architecture

- **Frontend**: React 18 with Tailwind CSS
- **Backend**: FastAPI (Python) with faster-whisper
- **Transcription**: OpenAI Whisper Large-V3 via CTranslate2
- **Speaker Diarization**: pyannote-audio 3.1
- **Engine compatibility**: see [`docs/engines.md`](docs/engines.md) for which fixes/features apply to which transcription backend.

## Quick Start

### Prerequisites

1. **ffmpeg** (required for audio extraction)
   ```bash
   # macOS
   brew install ffmpeg
   ```

2. **HuggingFace Token** (required for speaker diarization rate limits)
   - Get a read-only token at: https://huggingface.co/settings/tokens
   - The model at https://huggingface.co/pyannote/speaker-diarization-community-1 is open-source — no terms acceptance required

3. **Environment Setup**
   ```bash
   cp .env.example .env
   # Edit .env with your HuggingFace token
   ```

---

## Deployment Options

### Option 1: MacBook Only (Recommended for Development)

Run everything on your MacBook M3 for best performance:

```bash
# One command to start everything
./scripts/start-all.sh
```

Or start services separately:

```bash
# Terminal 1: Start backend
./scripts/start-backend.sh

# Terminal 2: Start frontend
./scripts/start-frontend.sh
```

**Access:**
- Frontend: http://localhost:3000
- Backend: http://localhost:8000

**Stop all services:**
```bash
./scripts/stop-all.sh
```

### Option 2: Hybrid (NAS Frontend + MacBook Backend)

Best for always-on access with optimal ML performance:

| Component | Location | Why |
|-----------|----------|-----|
| Frontend | NAS (DXP 4800 Plus) | Always available, low power |
| Backend | MacBook M3 | Best Whisper performance |

#### Step 1: Start Backend on MacBook

```bash
./scripts/start-backend.sh
```

Note your MacBook's IP address (shown in the output).

#### Step 2: Deploy Frontend on NAS

Copy the project to your NAS, then:

```bash
cd /path/to/project/deploy/nas
./setup.sh 192.168.1.100  # Replace with your MacBook IP
```

**Access:** http://your-nas-ip:3000

#### Step 3: When Not Using

- NAS frontend stays running (low resource usage)
- Stop MacBook backend when not transcribing
- Frontend will show connection error until backend starts

### Option 3: Docker Compose (Local)

Run both services in Docker on your MacBook:

```bash
# Set your HuggingFace token
export HF_TOKEN="your_token"

# Start both services
docker-compose -f docker-compose.local.yml up --build
```

> **Note:** Native scripts (Option 1) offer better M3 performance than Docker.

---

## Manual Setup

### Backend

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

### Frontend

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
| `HF_TOKEN` | - | HuggingFace token for speaker diarization (required) |
| `WHISPER_MODEL_SIZE` | `large-v3` | Model size (`tiny`, `base`, `small`, `medium`, `large-v3`) |

The backend automatically detects Apple Silicon and configures optimal settings.

### Frontend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REACT_APP_API_URL` | `http://localhost:8000` | Backend API URL |

## API Endpoints

### Transcription

#### `POST /transcribe/file`
Upload and transcribe an audio/video file.

**Query Parameters:**
- `language`: Language code (`en`, `fr`, or `auto`)
- `enable_diarization`: Enable speaker identification (default: true)
- `enable_noise_reduction`: Apply noise reduction before transcription (default: false)

#### `POST /transcribe/youtube`
Download and transcribe audio from a YouTube URL.

**Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "language": "auto",
  "enable_diarization": true,
  "enable_noise_reduction": false
}
```

#### `POST /transcribe/batch`
Upload and transcribe multiple files simultaneously.

**Query Parameters:**
- `language`: Language code (`en`, `fr`, or `auto`)
- `enable_diarization`: Enable speaker identification (default: true)

**Response:**
```json
{
  "batch_id": "uuid",
  "job_ids": ["uuid1", "uuid2", ...],
  "total": 3
}
```

### Job Management

#### `GET /job/{job_id}`
Get transcription status and results.

#### `GET /batch/{batch_id}`
Get batch transcription status with individual job progress.

#### `GET /job/{job_id}/export?format=txt`
Export transcript in specified format: `txt`, `md`, `srt`, `pdf`, `docx`

### Editing

#### `PUT /job/{job_id}/segments`
Update transcript segments with edited text.

**Body:**
```json
{
  "segments": [
    {"start": 0.0, "end": 2.5, "text": "Hello world", "speaker": "John"}
  ]
}
```

#### `PUT /job/{job_id}/speakers`
Rename speaker labels in a completed transcription.

**Body:**
```json
{
  "speaker_mapping": {
    "SPEAKER_00": "John",
    "SPEAKER_01": "Jane"
  }
}
```

#### `GET /job/{job_id}/search?q=text`
Search for text within a transcript.

**Query Parameters:**
- `q`: Search query (required)
- `case_sensitive`: Case-sensitive search (default: false)

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

## Project Structure

```
whisper-transcription-app/
├── backend/
│   ├── main.py              # FastAPI server with Whisper
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile           # Backend container
├── src/
│   └── App.js               # React frontend
├── deploy/
│   └── nas/
│       ├── docker-compose.yml  # NAS deployment config
│       ├── Dockerfile          # Frontend container
│       ├── nginx.conf          # Nginx configuration
│       └── setup.sh            # NAS setup script
├── scripts/
│   ├── start-backend.sh     # Start backend server
│   ├── start-frontend.sh    # Start frontend dev server
│   ├── start-all.sh         # Start everything
│   └── stop-all.sh          # Stop all services
├── docker-compose.local.yml # Local Docker deployment
├── .env.example             # Environment template
└── README.md
```

## Troubleshooting

### Backend won't start
- Check Python 3.11+ is installed: `python3 --version`
- Ensure ffmpeg is installed: `brew install ffmpeg`
- Check port 8000 is free: `lsof -i:8000`

### Speaker diarization not working
- Verify HF_TOKEN is set correctly (a read-only token suffices)
- Confirm network access to https://huggingface.co/pyannote/speaker-diarization-community-1 (open-source, no terms acceptance)

### Frontend can't connect to backend
- Ensure backend is running: `curl http://localhost:8000/health`
- Check REACT_APP_API_URL in frontend
- For NAS: verify MacBook IP is correct and firewall allows port 8000

### Slow transcription
- First run downloads the model (~3GB)
- Subsequent runs use cached model
- Large files take longer; expect ~0.5-1x real-time on M3

## License

MIT
