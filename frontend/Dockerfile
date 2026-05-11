FROM node:22-slim AS builder

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9 --activate

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_PUBLISHABLE_OR_ANON_KEY
ARG NEXT_PUBLIC_BACKEND_URL

RUN pnpm build

FROM node:22-slim AS runner

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9 --activate

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
COPY --from=builder /app/next.config.js ./

EXPOSE 3000

CMD ["pnpm", "start"]
