# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Next.js frontend — bun for install/build, node-slim for the standalone
# runtime so the final image stays small.
# ---------------------------------------------------------------------------
FROM oven/bun:1.3 AS deps
WORKDIR /app
COPY package.json bun.lockb* bunfig.toml* ./
RUN bun install --frozen-lockfile

FROM oven/bun:1.3 AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN bun run build

# ---------------------------------------------------------------------------
FROM node:20-slim AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN groupadd --system --gid 1001 nextjs \
    && useradd  --system --uid 1001 --gid nextjs nextjs

WORKDIR /app

# Standalone output (recommended). Falls back to copying full .next if standalone is not enabled.
COPY --from=builder --chown=nextjs:nextjs /app/public ./public
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://localhost:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
