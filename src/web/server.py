import os
import sys
import yaml
import json
import asyncio
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

from src.bot import LinkedInEasyApplyBot
from src.tracker import ApplicationTracker

app = FastAPI(title="ApplyFlow AI Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = "config.yaml"
RESUMES_DIR = Path("resumes")
RESUMES_DIR.mkdir(exist_ok=True)
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

class LogBroadcaster:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logs_history: List[Dict[str, Any]] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send buffered recent logs
        for log in self.logs_history[-50:]:
            await websocket.send_json(log)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str, level: str = "info", meta: Optional[Dict] = None):
        log_entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "message": message,
            "level": level,
            "meta": meta or {}
        }
        self.logs_history.append(log_entry)
        if len(self.logs_history) > 500:
            self.logs_history.pop(0)

        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(log_entry)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)

broadcaster = LogBroadcaster()
main_loop: Optional[asyncio.AbstractEventLoop] = None

# Bot state management
class BotState:
    is_running: bool = False
    current_task: Optional[str] = None
    last_run_time: Optional[str] = None
    next_run_time: Optional[str] = None
    schedule_interval_hours: int = 12
    schedule_enabled: bool = False

state = BotState()
scheduler = BackgroundScheduler()
scheduler.start()

@app.on_event("startup")
async def on_startup():
    global main_loop, state
    main_loop = asyncio.get_running_loop()
    
    # Cargar y activar programador automáticamente si estaba habilitado
    try:
        cfg = load_config()
        sched_cfg = cfg.get("scheduler", {})
        if sched_cfg.get("enabled", False):
            interval = sched_cfg.get("interval_hours", 12)
            state.schedule_enabled = True
            state.schedule_interval_hours = interval
            
            def job_wrapper():
                c = load_config()
                execute_bot_cycle(c, main_loop)
                
            scheduler.add_job(job_wrapper, 'interval', hours=interval, id="auto_apply_job")
            print(f"[SCHEDULER] Auto-pilot initialized: running every {interval} hours.")
    except Exception as e:
        print(f"[SCHEDULER] Startup warning: {e}")

def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        raise HTTPException(status_code=404, detail="config.yaml not found")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_config(config_data: Dict[str, Any]):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config_data, f, allow_unicode=True, sort_keys=False)

def check_linkedin_session() -> bool:
    profile_dir = Path("data/browser_profile")
    if not profile_dir.exists():
        return False
    default_dir = profile_dir / "Default"
    return default_dir.exists() and (default_dir / "Cookies").exists()

# Custom logger hook for the bot to stream logs via WebSockets
class WebLoggerHook:
    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.loop = loop or main_loop

    def log(self, message: str, level: str = "info", meta: Optional[Dict] = None):
        target_loop = self.loop or main_loop
        if target_loop and target_loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcaster.broadcast(message, level, meta), target_loop)
        else:
            print(f"[{level.upper()}] {message}")

def execute_bot_cycle(config: Dict[str, Any], loop: asyncio.AbstractEventLoop):
    global state
    state.is_running = True
    state.last_run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hook = WebLoggerHook(loop)
    
    hook.log("🚀 Starting autonomous application pipeline...", "info")
    try:
        bot = LinkedInEasyApplyBot(config)
        
        # Override bot logging to stream to WebUI
        bot_run_searches(bot, hook)
        hook.log("🏁 Cycle completed successfully.", "success")
    except Exception as e:
        hook.log(f"❌ Error in execution cycle: {str(e)}", "error")
    finally:
        state.is_running = False
        state.current_task = None
        hook.log("💤 Engine idle. Waiting for next trigger.", "info")

def bot_run_searches(bot: LinkedInEasyApplyBot, hook: WebLoggerHook):
    from playwright.sync_api import sync_playwright
    searches = bot.config.get("job_searches", [])
    
    with sync_playwright() as p:
        context = bot.launch_browser(p)
        page = context.new_page()
        page.set_default_timeout(45000)

        try:
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=45000)
            bot.sleep_random(1.0)
        except Exception:
            pass

        if "login" in page.url or "checkpoint" in page.url:
            hook.log("⚠️ No active LinkedIn session. Please authenticate via Web Dashboard.", "warning")
            context.close()
            return

        hook.log("🔐 Authenticated with LinkedIn successfully.", "success")

        for search_item in searches:
            if bot.applied_count >= bot.max_applications:
                hook.log(f"🛑 Reached daily quota limit ({bot.max_applications} apps).", "warning")
                break

            query = search_item.get("query", "")
            location = search_item.get("location", "")
            profile_type = search_item.get("type", "default")

            hook.log(f"🔍 Searching: '{query}' ({location}) [Profile: {profile_type}]", "info")
            search_url = bot.build_search_url(query, location)
            
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
                bot.sleep_random(1.5)
            except Exception as e:
                hook.log(f"⚠️ Search page load timeout: {e}", "warning")
                continue

            job_cards = page.query_selector_all(".jobs-search-results-list li.jobs-search-results__list-item, div.job-card-container, div[data-occludable-job-id]")
            hook.log(f"Found {len(job_cards)} job postings on current batch.", "info")

            for card in job_cards:
                if bot.applied_count >= bot.max_applications:
                    break

                try:
                    import re
                    job_id = card.get_attribute("data-occludable-job-id") or card.get_attribute("data-job-id")
                    if not job_id:
                        link_elem = card.query_selector("a.job-card-list__title, a.job-card-container__link")
                        if link_elem:
                            href = link_elem.get_attribute("href") or ""
                            match = re.search(r"view/(\d+)", href)
                            if match:
                                job_id = match.group(1)

                    if not job_id or bot.tracker.is_already_applied(job_id):
                        continue

                    card.scroll_into_view_if_needed()
                    card.click()
                    bot.sleep_random(0.8)

                    title_elem = page.query_selector(".job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, h1.t-24")
                    title = title_elem.inner_text().strip() if title_elem else "Role"

                    company_elem = page.query_selector(".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name")
                    company = company_elem.inner_text().split("·")[0].strip() if company_elem else "Company"

                    location_elem = page.query_selector(".job-details-jobs-unified-top-card__bullet, .jobs-unified-top-card__bullet")
                    loc_text = location_elem.inner_text().strip() if location_elem else ""

                    is_relevant, reason = bot.is_title_relevant(title)
                    if not is_relevant:
                        hook.log(f"⏭ Filtered out non-tech role: '{title}' ({reason})", "muted")
                        continue

                    hook.log(f"🎯 Evaluating Tech Role: '{title}' @ {company}", "info")

                    apply_btn = page.query_selector("button.jobs-apply-button, button.jobs-apply-button--top-card")
                    if not apply_btn or not any(text in apply_btn.inner_text() for text in ["Easy Apply", "Solicitud sencilla", "Solicitar"]):
                        hook.log("ℹ External application required (No Easy Apply), skipping.", "muted")
                        continue

                    apply_btn.click()
                    bot.sleep_random(1.2)

                    success, note = bot.handle_easy_apply_modal(page, profile_type, title)
                    job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"

                    if success:
                        bot.applied_count += 1
                        hook.log(f"✅ SUBMITTED: '{title}' @ {company} ({bot.applied_count}/{bot.max_applications})", "success", {
                            "title": title, "company": company, "url": job_url
                        })
                        bot.tracker.record_application(job_id, title, company, loc_text, job_url, query, "APPLIED", note)
                    else:
                        hook.log(f"⏩ Skipped ({note}): '{title}' @ {company}", "warning")
                        bot.tracker.record_application(job_id, title, company, loc_text, job_url, query, "SKIPPED", note)

                    bot.sleep_random(1.5)

                except Exception as e:
                    hook.log(f"Error evaluating card: {e}", "warning")
                    continue

        context.close()
        bot.tracker.export_to_csv()

# REST Endpoints
@app.get("/api/status")
def get_status():
    config = load_config()
    tracker = ApplicationTracker(config.get("bot_settings", {}).get("database_path", "data/applications.db"))
    stats = tracker.get_stats()
    return {
        "is_running": state.is_running,
        "linkedin_connected": check_linkedin_session(),
        "stats": stats,
        "last_run": state.last_run_time,
        "schedule_enabled": state.schedule_enabled,
        "schedule_interval_hours": state.schedule_interval_hours
    }

@app.post("/api/run/start")
async def start_run():
    if state.is_running:
        return {"status": "already_running"}
    config = load_config()
    loop = asyncio.get_running_loop()
    threading.Thread(target=execute_bot_cycle, args=(config, loop), daemon=True).start()
    return {"status": "started"}

@app.post("/api/auth/login")
def trigger_auth():
    if state.is_running:
        raise HTTPException(status_code=400, detail="Bot is currently running a cycle")
    
    def run_login():
        config = load_config()
        bot = LinkedInEasyApplyBot(config)
        bot.interactive_login()

    threading.Thread(target=run_login, daemon=True).start()
    return {"status": "login_window_opened"}

@app.get("/api/config")
def get_config_endpoint():
    return load_config()

@app.post("/api/config")
def update_config_endpoint(new_config: Dict[str, Any]):
    save_config(new_config)
    return {"status": "saved", "config": new_config}

@app.get("/api/jobs")
def get_jobs_endpoint():
    config = load_config()
    tracker = ApplicationTracker(config.get("bot_settings", {}).get("database_path", "data/applications.db"))
    import sqlite3
    with sqlite3.connect(tracker.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM applications ORDER BY applied_date DESC LIMIT 100")
        rows = [dict(r) for r in cursor.fetchall()]
    return {"jobs": rows, "stats": tracker.get_stats()}

@app.get("/api/jobs/export")
def export_jobs_endpoint():
    config = load_config()
    tracker = ApplicationTracker(config.get("bot_settings", {}).get("database_path", "data/applications.db"))
    csv_file = tracker.export_to_csv()
    return FileResponse(csv_file, media_type="text/csv", filename="applied_jobs_report.csv")

@app.get("/api/resumes/list")
def list_resumes():
    files = []
    for p in RESUMES_DIR.glob("*.pdf"):
        files.append({
            "name": p.name,
            "size_kb": round(p.stat().st_size / 1024, 1),
            "modified": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        })
    return {"resumes": files}

@app.post("/api/resumes/upload")
async def upload_resume(file: UploadFile = File(...), target_slot: str = Form(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    filename = f"CV_Paulo_Espinoza_{target_slot}.pdf" if target_slot in ["FullStack", "DataAnalyst"] else file.filename
    dest = RESUMES_DIR / filename
    
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)
        
    return {"status": "uploaded", "filename": filename, "path": str(dest)}

@app.post("/api/scheduler/update")
def update_scheduler(enabled: bool = Form(...), interval_hours: int = Form(...)):
    global state
    state.schedule_enabled = enabled
    state.schedule_interval_hours = interval_hours
    
    # Guardar en config.yaml para que sobreviva a reinicios
    try:
        cfg = load_config()
        cfg["scheduler"] = {
            "enabled": enabled,
            "interval_hours": interval_hours
        }
        save_config(cfg)
    except Exception as e:
        print(f"[SCHEDULER] Warning saving config: {e}")

    scheduler.remove_all_jobs()
    if enabled and interval_hours > 0:
        def job_wrapper():
            c = load_config()
            execute_bot_cycle(c, main_loop)
        scheduler.add_job(job_wrapper, 'interval', hours=interval_hours, id="auto_apply_job")
        
    return {
        "status": "updated",
        "schedule_enabled": state.schedule_enabled,
        "interval_hours": state.schedule_interval_hours
    }

@app.websocket("/ws/logs")
async def websocket_logs_endpoint(websocket: WebSocket):
    await broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)

# Mount static web dashboard
STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
