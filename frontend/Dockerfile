FROM node:22-alpine

RUN apk add --no-cache libc6-compat

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --fetch-retries=5 --fetch-retry-factor=2 --fetch-retry-mintimeout=20000 --fetch-retry-maxtimeout=120000

COPY . .

ARG NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-http://localhost:8000}
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# API_URL é do processo em execução, não deste build. O Compose define-a.

RUN npm run build

EXPOSE ${WEB_PORT:-3000}

CMD ["npm", "start"]
