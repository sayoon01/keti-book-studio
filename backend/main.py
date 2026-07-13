from fastapi import FastAPI
from sqlmodel import Session

from backend.api import books, config, outlines, personas, sources, units, visuals
from backend.storage.database import create_db_and_tables, engine
from backend.storage.persona_seed import seed_system_personas

app = FastAPI(title="KETI Book Studio API", version="0.6.0-phase6")


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
app.include_router(personas.router)
app.include_router(visuals.router)


@app.get("/health")
def health():
    return {"status": "ok", "phase": 6}
