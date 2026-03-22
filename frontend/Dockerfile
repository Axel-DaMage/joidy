FROM node:22-slim AS base
WORKDIR /app

FROM base AS deps
COPY package.json package-lock.json* ./
RUN npm ci

FROM deps AS build
COPY . .
RUN npm run build

FROM base AS production
COPY --from=build /app/build ./build
COPY --from=build /app/package.json .
ENV NODE_ENV=production
EXPOSE 3000
CMD ["node", "build"]

FROM deps AS development
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
