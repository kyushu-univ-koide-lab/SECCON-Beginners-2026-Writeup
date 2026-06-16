FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    xvfb \
    fonts-liberation \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/package*.json ./app/
RUN cd app && npm install --omit=dev

COPY app ./app
COPY extension ./extension
COPY public ./public
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENV NODE_ENV=production \
    PORT=3000 \
    CHROME_BIN=/usr/bin/chromium \
    BOT_BASE_URL=http://127.0.0.1:3000

EXPOSE 3000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
