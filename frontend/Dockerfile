FROM node:22-slim

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .

# NEXT_PUBLIC_* variables are inlined into the client bundle at build time, so
# unlike the backend's runtime environment variables this one must be supplied
# as a build arg (see docker-compose.yml/.prod.yml `build.args`), not just an
# `environment:` entry -- setting it only at `docker run`/compose-up time has
# no effect on an already-built image.
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
