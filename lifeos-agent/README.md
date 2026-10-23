# LifeOS Agent

A local-first AI productivity assistant. No paid API or API key is required.

## Features
- Task creation, editing, completion and deletion
- Daily planning with a deterministic scheduler
- Conflict-aware scheduling and rescheduling
- Local SQLite persistence
- Optional local AI through Ollama
- Rule-based fallback when Ollama is unavailable
- Activity history and productivity statistics
- Responsive web interface

## Requirements
- Python 3.10+
- Optional: Ollama for local AI (https://ollama.com/)

## Run on Windows
1. Extract this project.
2. Open a terminal in the `lifeos-agent` folder.
3. Create a virtual environment and install dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

4. Start the application:

```powershell
uvicorn app:app --reload
```

5. Open http://127.0.0.1:8000

## Optional local AI
Install Ollama, then download a model:

```powershell
ollama pull qwen2.5:3b
```

Keep Ollama running. LifeOS will try `http://localhost:11434`. If Ollama is unavailable, basic assistant commands still work using the built-in rule-based fallback.

You can change settings using environment variables:
- `OLLAMA_URL` (default `http://localhost:11434/api/chat`)
- `OLLAMA_MODEL` (default `qwen2.5:3b`)
- `LIFEOS_DB` (default `lifeos.db`)

## Notes
- This is a local single-user MVP; it does not implement authentication.
- The app does not connect to a real calendar or Alexa+.
- Confirm important changes before using the application for critical planning.
