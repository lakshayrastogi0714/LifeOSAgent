import os
import json
import sqlite3
import uuid
from datetime import datetime, date, time, timedelta
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

DB_PATH = os.getenv("LIFEOS_DB", "lifeos.db")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

app = FastAPI(title="LifeOS Agent", version="1.0.0")


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'pending',
            deadline TEXT,
            duration INTEGER NOT NULL DEFAULT 60,
            scheduled_start TEXT,
            scheduled_end TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)
        defaults = {
            "display_name": "there",
            "work_start": "09:00",
            "work_end": "18:00",
            "break_minutes": "10",
        }
        for key, value in defaults.items():
            con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, value))


init_db()


def log(action, details):
    with connect() as con:
        con.execute("INSERT INTO activity(action,details,created_at) VALUES(?,?,?)",
                    (action, details, now_iso()))


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    priority: str = "medium"
    deadline: Optional[str] = None
    duration: int = Field(default=60, ge=5, le=1440)


class TaskPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    priority: Optional[str] = None
    status: Optional[str] = None
    deadline: Optional[str] = None
    duration: Optional[int] = Field(default=None, ge=5, le=1440)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class SettingsIn(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=80)
    work_start: Optional[str] = None
    work_end: Optional[str] = None
    break_minutes: Optional[int] = Field(default=None, ge=0, le=90)


def row_task(row):
    return dict(row)


def get_task(task_id):
    with connect() as con:
        row = con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Task not found")
    return row_task(row)


def all_tasks(include_completed=True):
    query = "SELECT * FROM tasks"
    if not include_completed:
        query += " WHERE status != 'completed'"
    query += """ ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
                 WHEN 'medium' THEN 2 ELSE 3 END, deadline IS NULL, deadline ASC, created_at DESC"""
    with connect() as con:
        return [row_task(r) for r in con.execute(query).fetchall()]


def create_task(data: TaskIn):
    if data.priority not in {"low", "medium", "high", "urgent"}:
        raise HTTPException(400, "Priority must be low, medium, high, or urgent")
    task_id = str(uuid.uuid4())[:8]
    timestamp = now_iso()
    with connect() as con:
        con.execute("""INSERT INTO tasks
            (id,title,description,priority,status,deadline,duration,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (task_id, data.title.strip(), data.description, data.priority, "pending",
             data.deadline, data.duration, timestamp, timestamp))
    log("Task created", data.title.strip())
    return get_task(task_id)


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html"), encoding="utf-8") as f:
        return f.read()


@app.get("/api/health")
def health():
    ollama = False
    try:
        r = httpx.get(OLLAMA_URL.replace("/api/chat", "/api/tags"), timeout=1.2)
        ollama = r.status_code == 200
    except Exception:
        pass
    return {"status": "ok", "ollama_available": ollama, "model": OLLAMA_MODEL}


@app.get("/api/tasks")
def list_tasks(status: Optional[str] = None):
    tasks = all_tasks()
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    return tasks


@app.post("/api/tasks")
def add_task(data: TaskIn):
    return create_task(data)


@app.patch("/api/tasks/{task_id}")
def patch_task(task_id: str, data: TaskPatch):
    old = get_task(task_id)
    patch = data.model_dump(exclude_unset=True)
    if "priority" in patch and patch["priority"] not in {"low", "medium", "high", "urgent"}:
        raise HTTPException(400, "Invalid priority")
    if "status" in patch and patch["status"] not in {"pending", "in_progress", "completed"}:
        raise HTTPException(400, "Invalid status")
    patch["updated_at"] = now_iso()
    if patch.get("status") == "completed":
        patch["completed_at"] = now_iso()
    cols = list(patch.keys())
    if cols:
        with connect() as con:
            con.execute("UPDATE tasks SET " + ",".join(f"{c}=?" for c in cols) + " WHERE id=?",
                        [patch[c] for c in cols] + [task_id])
    log("Task updated", old["title"])
    return get_task(task_id)


@app.delete("/api/tasks/{task_id}")
def remove_task(task_id: str):
    task = get_task(task_id)
    with connect() as con:
        con.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    log("Task deleted", task["title"])
    return {"ok": True, "deleted": task_id}


def get_settings():
    with connect() as con:
        return {r["key"]: r["value"] for r in con.execute("SELECT * FROM settings")}


@app.get("/api/settings")
def settings():
    s = get_settings()
    return {
        "display_name": s.get("display_name", "there"),
        "work_start": s.get("work_start", "09:00"),
        "work_end": s.get("work_end", "18:00"),
        "break_minutes": int(s.get("break_minutes", "10")),
    }


@app.put("/api/settings")
def update_settings(data: SettingsIn):
    patch = data.model_dump(exclude_unset=True)
    if "work_start" in patch:
        try: time.fromisoformat(patch["work_start"])
        except Exception: raise HTTPException(400, "work_start must be HH:MM")
    if "work_end" in patch:
        try: time.fromisoformat(patch["work_end"])
        except Exception: raise HTTPException(400, "work_end must be HH:MM")
    for key, value in patch.items():
        if value is not None:
            with connect() as con:
                con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                            (key, str(value)))
    log("Settings updated", ", ".join(patch.keys()))
    return settings()


def plan_day():
    tasks = [t for t in all_tasks(False) if t["status"] != "completed"]
    s = get_settings()
    today = date.today()
    start = datetime.combine(today, time.fromisoformat(s.get("work_start", "09:00")))
    end = datetime.combine(today, time.fromisoformat(s.get("work_end", "18:00")))
    current = datetime.now()
    cursor = max(start, current.replace(tzinfo=None) if current.date() == today else start)
    blocks, unscheduled = [], []
    break_minutes = int(s.get("break_minutes", "10"))
    # Prefer overdue/soon deadlines, then priority; all completed work is excluded.
    priority_rank = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    tasks.sort(key=lambda t: (
        0 if t["deadline"] and t["deadline"][:10] < today.isoformat() else 1,
        t["deadline"] or "9999-12-31",
        priority_rank.get(t["priority"], 2)
    ))
    for task in tasks:
        duration = int(task["duration"])
        proposed_end = cursor + timedelta(minutes=duration)
        if proposed_end > end:
            unscheduled.append({"task": task, "reason": "Not enough working time remaining today"})
            continue
        blocks.append({
            "task_id": task["id"], "title": task["title"],
            "start": cursor.isoformat(timespec="minutes"),
            "end": proposed_end.isoformat(timespec="minutes"),
            "duration": duration, "priority": task["priority"]
        })
        cursor = proposed_end + timedelta(minutes=break_minutes)
    return {"date": today.isoformat(), "blocks": blocks, "unscheduled": unscheduled,
            "note": "This is a proposed plan. It does not alter saved tasks until you apply it."}


@app.get("/api/plan")
def get_plan():
    return plan_day()


@app.post("/api/plan/apply")
def apply_plan():
    plan = plan_day()
    with connect() as con:
        for block in plan["blocks"]:
            con.execute("""UPDATE tasks SET scheduled_start=?, scheduled_end=?, updated_at=?
                           WHERE id=? AND status != 'completed'""",
                        (block["start"], block["end"], now_iso(), block["task_id"]))
    log("Daily plan applied", f"{len(plan['blocks'])} tasks scheduled")
    return {"ok": True, **plan}


@app.get("/api/activity")
def activity():
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM activity ORDER BY id DESC LIMIT 50")]


@app.get("/api/stats")
def stats():
    tasks = all_tasks()
    today = date.today().isoformat()
    completed = [t for t in tasks if t["status"] == "completed"]
    overdue = [t for t in tasks if t["status"] != "completed" and t["deadline"] and t["deadline"][:10] < today]
    return {
        "total": len(tasks),
        "completed": len(completed),
        "pending": sum(1 for t in tasks if t["status"] != "completed"),
        "overdue": len(overdue),
        "completion_rate": round(100 * len(completed) / len(tasks)) if tasks else 0
    }


async def ask_ollama(message, tasks):
    prompt = (
        "You are LifeOS, a concise personal productivity assistant. "
        "Do not claim you changed data; backend tools are separate. "
        "Use only the supplied task data for claims about tasks. Suggest practical next steps.\n"
        f"Current date: {date.today().isoformat()}\n"
        f"Tasks JSON: {json.dumps(tasks, ensure_ascii=False)}\n"
        f"User message: {message}"
    )
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        })
        response.raise_for_status()
        return response.json()["message"]["content"]


def fallback_reply(message, tasks):
    text = message.lower()
    if any(w in text for w in ["plan", "schedule", "organize my day"]):
        plan = plan_day()
        lines = [f"{b['start'][11:16]}–{b['end'][11:16]}  {b['title']}" for b in plan["blocks"]]
        answer = "Here is your proposed plan:\n" + ("\n".join(lines) if lines else "No tasks fit into today's remaining working hours.")
        if plan["unscheduled"]:
            answer += "\n\nUnscheduled:\n" + "\n".join(x["task"]["title"] + " — " + x["reason"] for x in plan["unscheduled"])
        answer += "\n\nUse the Schedule page to review and apply this plan."
        return answer
    if "urgent" in text or "priority" in text or "focus" in text:
        active = [t for t in tasks if t["status"] != "completed"]
        active.sort(key=lambda t: ({"urgent":0,"high":1,"medium":2,"low":3}.get(t["priority"],2), t["deadline"] or "9999"))
        return "Your highest-priority active tasks:\n" + ("\n".join(f"• {t['title']} — {t['priority']}, deadline {t['deadline'] or 'not set'}" for t in active[:5]) or "No active tasks yet.")
    return ("I'm running in local fallback mode because Ollama is not connected. I can still help with tasks and planning through the dashboard. "
            "Try: 'plan my day', 'what should I focus on?', or create a task using the Tasks page.")


@app.post("/api/chat")
async def chat(data: ChatIn):
    message = data.message.strip()
    tasks = all_tasks()
    try:
        reply = await ask_ollama(message, tasks)
        mode = "ollama"
    except Exception:
        reply = fallback_reply(message, tasks)
        mode = "fallback"
    log("Assistant message", message[:180])
    return {"reply": reply, "mode": mode}


@app.post("/api/demo/seed")
def seed_demo():
    existing = all_tasks()
    if existing:
        return {"ok": True, "message": "Database already contains tasks; no demo data added."}
    examples = [
        TaskIn(title="Review data structures", description="Revise trees, graphs and complexity", priority="urgent", deadline=(date.today()+timedelta(days=1)).isoformat(), duration=90),
        TaskIn(title="Digital logic practice", description="Solve flip-flop and counter questions", priority="high", deadline=(date.today()+timedelta(days=2)).isoformat(), duration=60),
        TaskIn(title="Build LifeOS UI", description="Polish dashboard and task list", priority="medium", deadline=(date.today()+timedelta(days=3)).isoformat(), duration=120),
    ]
    for item in examples:
        create_task(item)
    return {"ok": True, "message": "Demo tasks created."}
