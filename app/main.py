import ipaddress
import logging
import os
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.database import init_db
from app.routers import meals, plans, ai, settings, inventory

_app_log = logging.getLogger("dinner.app")
_access_log = logging.getLogger("dinner.access")


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # Replace uvicorn's per-request access log with our own middleware
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def _real_ip(request: Request) -> str:
    """Extract the real client IP, preferring Traefik-set headers."""
    return (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "-")
    )


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log every non-static request with real client IP and response time."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000

        if request.url.path.startswith("/static/"):
            return response

        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        _access_log.log(
            level,
            '%s "%s %s" %d %.0fms',
            _real_ip(request),
            request.method,
            request.url.path,
            response.status_code,
            ms,
        )
        return response


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

        try:
            client_ip = ipaddress.ip_address(_real_ip(request))
        except ValueError:
            return Response("Forbidden", status_code=403)

        if any(client_ip in net for net in networks):
            return await call_next(request)

        return Response("Forbidden", status_code=403)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    init_db()
    provider = os.getenv("AI_PROVIDER", "anthropic")
    _app_log.info("What's For Dinner started | AI provider=%s", provider)
    yield
    _app_log.info("Shutting down")


app = FastAPI(title="What's For Dinner", version="1.0.0", lifespan=lifespan)

app.include_router(settings.router)
app.include_router(meals.router)
app.include_router(plans.router)
app.include_router(ai.router)
app.include_router(inventory.router)

app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS — configured via ALLOWED_ORIGINS env var (default: wildcard)
_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _origins_env.split(",")] if _origins_env != "*" else ["*"]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])

# Subnet restriction
app.add_middleware(SubnetMiddleware)

# Access log — outermost so it captures every request (including 403s from SubnetMiddleware)
app.add_middleware(AccessLogMiddleware)


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/{full_path:path}")
def catch_all(full_path: str):
    return FileResponse("static/index.html")
