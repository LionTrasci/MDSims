FROM node:22-bookworm-slim AS frontend
WORKDIR /web
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt && useradd --uid 10001 --create-home portal && mkdir -p /data && chown portal:portal /data
COPY backend/app ./app
COPY --from=frontend /web/dist /static
ENV PORTAL_DATA=/data PORTAL_STATIC=/static PORTAL_CONFIG=/config/config.json
USER portal
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
