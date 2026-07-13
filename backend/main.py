from fastapi import FastAPI

from backend.api import books, config, outlines, units
from backend.storage.database import create_db_and_tables

app = FastAPI(title="KETI Book Studio API", version="0.1.0-phase1")


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


app.include_router(books.router)
app.include_router(config.router)
app.include_router(outlines.router)
app.include_router(units.router)


@app.get("/health")
def health():
    return {"status": "ok", "phase": 1}