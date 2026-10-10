# Fireline web: builds the React app, then serves it and the API from one FastAPI process.
FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY server/ server/
COPY --from=web /web/dist web/dist
ENV FIRELINE_DB=/data/fireline.db \
    FIRELINE_WEB_DIST=/app/web/dist
VOLUME /data
EXPOSE 8000
WORKDIR /app/server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
