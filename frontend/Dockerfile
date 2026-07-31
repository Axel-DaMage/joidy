FROM node:22-slim AS base
WORKDIR /app

FROM base AS deps
COPY package.json ./
RUN npm install

FROM deps AS development
COPY --chown=node:node . .
USER node
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM deps AS build
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
COPY . .
RUN npm run build

FROM base AS production
COPY --from=build --chown=node:node /app/build ./build
COPY --from=build --chown=node:node /app/package.json .
USER node
ENV NODE_ENV=production
EXPOSE 3000
CMD ["node", "build"]
