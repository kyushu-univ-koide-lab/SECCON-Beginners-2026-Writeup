FROM node:26-alpine@sha256:e71ac5e964b9201072425d59d2e876359efa25dc96bb1768cb73295728d6e4ea

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src ./src
COPY prisma ./prisma
COPY prisma.config.ts ./
RUN npx prisma generate

COPY public ./public
RUN npm run build

RUN adduser -D web && chown -R web:web /app
USER web

CMD ["npm", "start"]
