import ipaddress
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.database import init_db
from app.routers import meals, plans, ai, settings


class SubnetMiddleware(BaseHTTPMiddleware):
    """Block requests whose client IP is not in ALLOWED_SUBNETS (if set)."""

    async def dispatch(self, request: Request, call_next):
        subnets_env = os.getenv("ALLOWED_SUBNETS")
        if not subnets_env:
            return await call_next(request)

        networks = [
            ipaddress.ip_network(s.strip(), strict=False)
            for s in subnets_env.split(",")
            if s.strip()
        ]

        # Traefik sets X-Real-IP; fall back to the first IP in X-Forwarded-For,
        # then the raw socket address.
        client_ip_str = (
            request.headers.get("X-Real-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "")
        )

        try:
            client_ip = ipaddress.ip_address(client_ip_str)
        except ValueError:
            return Response("Forbidden", status_code=403)

        if any(client_ip in net for net in networks):
            return await call_next(request)

        return Response("Forbidden", status_code=403)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="What's For Dinner", version="1.0.0", lifespan=lifespan)

app.include_router(settings.router)
app.include_router(meals.router)
app.include_router(plans.router)
app.include_router(ai.router)

app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS — configured via ALLOWED_ORIGINS env var (default: wildcard)
_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _origins_env.split(",")] if _origins_env != "*" else ["*"]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])

# Subnet restriction — added after CORS so it runs first (outermost middleware)
app.add_middleware(SubnetMiddleware)


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/{full_path:path}")
def catch_all(full_path: str):
    return FileResponse("static/index.html")
