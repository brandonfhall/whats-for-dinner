# ── Stage 1: build Tailwind CSS + vendor Alpine.js ────────────────────────────
FROM node:20-slim AS frontend

WORKDIR /build

COPY package.json ./
RUN npm install

COPY tailwind.config.js ./
COPY static/ ./static/

# Compile Tailwind — scans static/ for class names, outputs a minified CSS file
RUN npx tailwindcss -i ./static/css/input.css -o ./static/css/tailwind.css --minify

# Copy Alpine.js from node_modules so the final image needs no internet access
RUN mkdir -p ./static/vendor && cp node_modules/alpinejs/dist/cdn.min.js ./static/vendor/alpine.min.js


# ── Stage 2: final Python image ────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY static/ ./static/

# Overwrite with build-stage outputs (compiled CSS + vendored Alpine.js)
COPY --from=frontend /build/static/css/tailwind.css ./static/css/tailwind.css
COPY --from=frontend /build/static/vendor/alpine.min.js ./static/vendor/alpine.min.js

RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV APP_PORT=8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT}"]
