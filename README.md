# AI Album Generator

Generate beautiful photo albums from raw images using AI-powered layout selection, story generation, and reference album analysis.

## Architecture

- **Frontend**: Next.js 14 + Tailwind CSS + React Dropzone
- **Backend**: FastAPI + Background Tasks
- **AI/ML**: OpenAI GPT-4o Vision, CLIP (deduplication), InsightFace (face detection)
- **PDF**: WeasyPrint

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## How It Works

1. **Upload** — Drag & drop 100–1000 photos + optional reference album (PDF/images)
2. **Preprocessing** — Resize, normalize, remove corrupted files
3. **Deduplication** — CLIP embeddings remove near-duplicate images
4. **Quality Filter** — OpenCV blur/exposure detection removes bad shots
5. **Face Detection** — InsightFace ranks images with clear faces higher
6. **Reference Analysis** — OpenAI Vision analyzes reference album layout patterns
7. **Story Generation** — LLM creates album sections (intro, events, highlights, closing)
8. **Layout Selection** — Rule-based filtering + AI picks from 10 JSON templates
9. **Rendering** — HTML album with CSS grid layouts
10. **PDF Export** — WeasyPrint converts to print-ready PDF

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Required for Vision + LLM features |
| `UPLOAD_DIR` | `./uploads` | Where uploaded files are stored |
| `OUTPUT_DIR` | `./output` | Where generated albums go |
| `MAX_UPLOAD_SIZE_MB` | `500` | Max file size per upload |
| `MAX_IMAGES` | `1000` | Max images per job |
