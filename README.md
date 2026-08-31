# Natya-AI

Natya-AI is a chat-first movie and TV recommendation application that combines conversational AI with personalized recommendation logic. Users chat with the system about mood, genres, actors, runtime, language, and more — and Natya-AI returns tailored movie/TV suggestions, rationale, and follow-up prompts to refine results.

Built with a Python backend (models, recommendation logic, API) and a JavaScript frontend (chat UI), Natya-AI is designed for experimentation and rapid prototyping of conversational recommendation experiences.

Key languages: Python (backend, AI), JavaScript (frontend)

## Features
- Natural-language chat interface for recommending movies and TV shows
- Preference-aware suggestions (genre, era, mood, actors, runtime, platform)
- Follow-up questioning to refine recommendations
- Pluggable model/provider support (local models, OpenAI, Hugging Face, etc.)
- REST API for chat and recommendation endpoints
- Example frontend demonstrating interactive chat UI

## Quickstart

Prerequisites
- Python 3.8+
- Node.js 16+ and npm or yarn
- (Optional) API keys for external services (e.g., TMDB, OpenAI)

1. Clone
   git clone https://github.com/PranavLabs/Natya-AI.git
   cd Natya-AI

2. Backend (Python)
   - Create and activate a virtual environment:
     python -m venv .venv
     source .venv/bin/activate  # macOS/Linux
     .venv\Scripts\activate     # Windows
   - Install dependencies:
     pip install -r requirements.txt
   - Create a `.env` file (example):
     MOVIEDB_API_KEY=your_tmdb_api_key_here
     OPENAI_API_KEY=your_openai_key_here
     NATYA_PORT=8000
   - Start the backend (example; adjust to your project layout):
     uvicorn app.main:app --reload --host 0.0.0.0 --port ${NATYA_PORT}
     or
     python app.py

3. Frontend (JavaScript)
   - cd web (or the frontend directory)
   - Install:
     npm install
     # or
     yarn install
   - Start dev server:
     npm run dev
     # or
     npm start
   - Open the UI at http://localhost:3000 (or the port shown by your frontend)

## API (example)
Replace paths below with the actual routes in your project if different.

- POST /api/chat
  - Purpose: Send a chat message and get a conversational reply + recommendations
  - Request JSON:
    {
      "user_id": "optional_user_id",
      "message": "I'm in the mood for a light sci-fi movie with strong female leads",
      "context": { "seen": ["Arrival"] }
    }
  - Response JSON (example):
    {
      "reply": "If you want light sci-fi with strong female leads, you might like 'Her' or 'Ex Machina'. Do you prefer recent releases or classics?",
      "recommendations": [
        { "title": "Ex Machina", "year": 2014, "why": "synthetic-intelligence theme, strong female lead (Alicia Vikander)" },
        { "title": "Her", "year": 2013, "why": "affectionate sci-fi, introspective tone" }
      ],
      "follow_up": "Do you want movies, TV shows, or both?"
    }

- GET /api/recommend?genre=drama&amp;limit=5
  - Purpose: Get non-chat bulk recommendations by filters

- POST /api/feedback
  - Purpose: Record user feedback on recommendations to improve personalization

Adjust route names and payloads to match your codebase.

## Configuration &amp; Environment Variables
Typical variables used by the project:
- TMDB_API_KEY — API key for The Movie Database (TMDb)
- SARVAM_API_KEY — API key for Sarvam AI
- SARVAM_MODEL — Model ID for Sarvam AI chat completions (default: `sarvam-105b`, alternative: `sarvam-105b-conversations`)
- SARVAM_CHAT_URL — Sarvam chat completions endpoint (default: `https://api.sarvam.ai/v1/chat/completions`)
- NATYA_PORT — backend port (default 8000)
- FRONTEND_API_URL — backend base URL used by the frontend

Store secrets in a `.env` file and never commit them to git.

## Data, Privacy &amp; Usage Notes
- Recommendations may use third-party APIs (TMDB, OMDB). Respect their TOS when caching or storing metadata.
- If you store user chats or preference data, update the README to explain retention and privacy practices.
- Provide an opt-out or delete mechanism for stored user data in production.

## Example usage (curl)
Send a message to the chat endpoint and get recommendations:
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"guest-1","message":"Recommend a gritty crime series with strong character development."}'

## Project layout (typical)
- app/ or src/ — Python backend (API, recommender, model wrappers)
- web/ — frontend (React/Vue/Svelte chat UI)
- data/ — local datasets, caches
- examples/ — example scripts to run inference or demos
- requirements.txt — Python deps
- package.json — frontend deps

If your repo uses different directories, update these paths accordingly.

## Testing
- Backend: pytest tests/
- Frontend: npm test (as configured in package.json)

## Deployment ideas
- Dockerize backend and frontend; provide docker-compose for local one-command setup
- Add a simple worker for asynchronous model calls and caching
- Use environment-specific configuration and secrets (GitHub Actions, Vercel, Render)

## Contributing
We welcome help! Typical workflow:
1. Open an issue describing the feature or bug.
2. Fork the repo and create a branch.
3. Add tests and documentation for your change.
4. Open a pull request referencing the issue.

## Roadmap ideas
- Personalization via lightweight user profiles
- Hybrid recommender: collaborative signals + LLM re-ranking
- Multi-turn conversation memory with explicit slot-filling
- Mobile-friendly chat UI and voice input

## License
Add your license here (e.g., MIT). Consider adding a LICENSE file to the repo.

## Maintainer / Contact
PranavLabs — GitHub: @PranavLabs
