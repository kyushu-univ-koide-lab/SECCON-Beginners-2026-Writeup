FROM node:26-alpine@sha256:e71ac5e964b9201072425d59d2e876359efa25dc96bb1768cb73295728d6e4ea

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY . .

ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

RUN adduser -D web && chown -R web:web /app
USER web

ENV PORT=33456

CMD ["npm", "run", "start"]
