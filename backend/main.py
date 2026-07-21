from fastapi import FastAPI
from sqlmodel import Session

from backend.api import books, chat, chat_v2, config, exports, outlines, personas, sources, traces, units, versions, visuals
from backend.api.source_library import router as source_library_router
from backend.storage.database import create_db_and_tables, engine
from backend.storage.persona_seed import seed_system_personas

app = FastAPI(title="KETI Book Studio API", version="0.10.0-phase10c-step3")


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    with Session(engine) as session:
        seed_system_personas(session)


app.include_router(books.router)
app.include_router(config.router)
app.include_router(outlines.router)
app.include_router(units.router)
app.include_router(sources.router)
app.include_router(source_library_router)
app.include_router(personas.router)
app.include_router(visuals.router)
app.include_router(chat.router)
app.include_router(versions.router)
app.include_router(exports.router)
app.include_router(traces.router)
app.include_router(chat_v2.router)


@app.get("/health")
def health():
    return {"status": "ok", "phase": "10c-step3"}
