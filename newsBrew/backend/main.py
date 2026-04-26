from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database.database import init_db, AsyncSessionLocal
from routers import keywords, settings, archives, brew
from ws.manager import manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with AsyncSessionLocal() as db:
        from services.env_seed import seed_settings_from_env
        await seed_settings_from_env(db)

        from database.models import Setting
        from sqlalchemy import select as sa_select
        result = await db.execute(sa_select(Setting).where(Setting.key == "schedule_time"))
        setting = result.scalar_one_or_none()
        schedule_time = setting.value if setting else "08:00"
    from services.scheduler import setup_scheduler, start_scheduler, stop_scheduler
    setup_scheduler(schedule_time)
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(title="News Brew API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",  # Vite fallback port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(keywords.router)
app.include_router(settings.router)
app.include_router(archives.router)
app.include_router(brew.router)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
