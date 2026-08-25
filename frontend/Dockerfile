ARG NODE_VERSION=22

FROM node:${NODE_VERSION}-slim AS base
WORKDIR /app

FROM base AS deps
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
RUN chown -R node:node /app

FROM deps AS development
# Run the dev server as the host UID/GID (passed via docker-compose.dev.yml build
# args, defaulting to 1000). With a bind-mounted ./frontend:/app this ensures
# svelte-kit sync writes frontend/.svelte-kit/* owned by the host user, so no
# sudo is ever needed to clean them — even when the host UID is not 1000 (#886).
ARG UID=1000
ARG GID=1000
RUN getent group ${GID} >/dev/null || groupadd -g ${GID} appuser \
 && id -u ${UID} >/dev/null 2>&1 || useradd -u ${UID} -g ${GID} -m -s /bin/bash appuser
RUN chown -R ${UID}:${GID} /app
COPY --chown=${UID}:${GID} . .
USER ${UID}:${GID}
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM deps AS build
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
ENV NODE_OPTIONS=--max-old-space-size=4096

COPY --chown=node:node . .

USER node
RUN npm run build

FROM base AS production
COPY --from=build --chown=node:node /app/build ./build
COPY --from=build --chown=node:node /app/package.json .
COPY --from=build --chown=node:node /app/package-lock.json .
RUN --mount=type=cache,target=/root/.npm npm ci --omit=dev --ignore-scripts
RUN chown -R node:node /app
USER node
ENV NODE_ENV=production
EXPOSE 3000
CMD ["node", "build"]
