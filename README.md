# Praveen Kehelella — portfolio

Personal site for an agentic AI developer: selected work, a case-study gallery, and a terminal that answers questions about the bio.

Static HTML and JSON on the front. A small FastAPI process serves the files and streams the terminal agent.

## Run locally

Python 3.11+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

Put an OpenAI key in `.env` (`OPENAI_API_KEY`). Without it the site still loads; the terminal agent returns 503.

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Work case studies live at `/completed_work/`.

## Docker

`.env` is required (same keys as `.env.example`). It is not copied into the image; Compose injects it at runtime.

```bash
docker compose up --build
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Stop with Ctrl+C, or `docker compose down`.

`.env` is gitignored. Do not commit a real key. `.env.example` is the public template.

Also gitignored: the resume and cover-letter files, plus live-product screenshots that show admin UIs, booking IDs, or other people’s contact details. Keep those on disk if you want them; they will not be in git and the app will not serve them.

## Layout

| Path | Role |
| --- | --- |
| `index.html` | Home: about, career, selected work, terminal, contact |
| `images/` | Portrait stills used on the home hero |
| `fonts/` | Self-hosted typefaces |
| `config.json` | Section visibility (`about`, `experience`, `work`, `demos`, `products`, `terminal`, `contact`) |
| `projects.json` | Project cards and terminal `projects` command |
| `completed_work/details.json` | Case-study writeups and screenshot lists |
| `completed_work/<slug>/` | Thumbs and slides for each project |
| `backend/profile.md` | Identity and experience fed to the terminal agent |
| `backend/main.py` | FastAPI app: static files + `POST /api/chat` |
| `backend/knowledge.py` | Builds the agent system prompt from profile + projects |
| `Dockerfile` | Production image: uvicorn on port 8000 |
| `docker-compose.yml` | Build + run, injects `.env` |

Edit JSON and markdown, then reload. `config.json` is fetched with `cache: no-store`.

## Terminal

Built-in commands (`help`, `whoami`, `skills`, `experience`, `projects`, `contact`, …) stay on the client. Anything else goes to `POST /api/chat` (SSE). The agent only answers from `profile.md` and `projects.json`. Rate limit is 8 requests per minute per IP.
