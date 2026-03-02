from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.routers import meals, plans, ai, settings

app = FastAPI(title="What's For Dinner", version="1.0.0")

app.include_router(settings.router)
app.include_router(meals.router)
app.include_router(plans.router)
app.include_router(ai.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/{full_path:path}")
def catch_all(full_path: str):
    return FileResponse("static/index.html")
