FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /srv
COPY adapter ./adapter
COPY backend ./backend
RUN pip install --no-cache-dir ./adapter ./backend
COPY --from=frontend /build/dist ./frontend/dist
ENV FRONTEND_DIST=/srv/frontend/dist
WORKDIR /srv/backend
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.agent.app:app --host 0.0.0.0 --port 8000"]
