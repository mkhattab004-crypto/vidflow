# VidFlow — Internal Video Production Platform

Automated YouTube video production from idea to export. Supports multiple channels and niches, Islamic content, AI script generation, and multi-format export.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | Python FastAPI |
| Database | PostgreSQL |
| Video | FFmpeg + Remotion |
| AI Script | Google Gemini API |
| TTS | Kokoro (local) |
| Stock | Pexels + Pixabay + Wikimedia |
| Islamic | Quran.com API + Sunnah.com API |

## Quick Start (Docker Compose)

```bash
# 1. Copy environment file
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

# 2. Start everything
docker-compose up -d

# Frontend: http://localhost
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `GEMINI_API_KEY` | Yes | Google Gemini API key (free) |
| `PEXELS_API_KEY` | Yes | Pexels API key (free) |
| `PIXABAY_API_KEY` | Yes | Pixabay API key (free) |
| `SECRET_KEY` | Yes | App secret key |

## Deploy on Railway

### Option 1: Full Stack via Docker Compose
1. Create a new project on Railway
2. Add a PostgreSQL database service
3. Deploy backend from `backend/` directory
4. Deploy frontend from `frontend/` directory
5. Set environment variables

### Option 2: Railway CLI
```bash
railway login
railway init
railway up
```

## Pages

| # | Page | Description |
|---|---|---|
| 1 | Channels | Manage YouTube channels, hooks, CTAs |
| 2 | Ideas | Generate and validate video ideas with AI |
| 3 | Content | AI script generation with Gemini |
| 4 | Visuals | Search and assign Pexels/Pixabay assets |
| 5 | Audio | TTS with Kokoro voices |
| 6 | Templates | Video format and Remotion effects |
| 7 | Review | 3-level review process |
| 8 | Export | Download MP4, script, metadata, subtitles |
| 9 | Projects | Full project history |

## Islamic Content

Full support for Islamic channels with:
- Quran.com API integration (all translations)
- Sunnah.com API (Bukhari, Muslim, and more)
- Mandatory 3-level review for Islamic content
- Image safety rules (no faces of prophets/companions)
- Arabic RTL text support
- Quran reciter voices (Abdulbasit, Husary, Afasy, etc.)

## Channels Included

- **CurioBuzz** — Facts & strange places (English)
- **Islamic EN** — Islamic content (English)
- **Islamic AR** — Islamic content (Arabic)
- **Islamic TR** — Islamic content (Turkish)
- **Finance** — Money & investing (English)
