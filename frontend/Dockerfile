# syntax=docker/dockerfile:1.7

FROM node:24-bookworm-slim AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run typecheck && npm run build

FROM caddy:2.8.4-alpine AS runtime
COPY docker/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/frontend/dist /srv/app
