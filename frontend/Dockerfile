# Frontend (Next.js) production image -- Section 15's move off Vercel onto a
# self-hosted DigitalOcean VPS (behind Coolify -- see docker-compose.yml at
# the repo root; this image is deployed exactly as-is, Coolify never needs
# to know it's Next.js).
#
# Three stages, genuinely worth it here (unlike the backend's single-stage
# Dockerfile): `npm install` pulls in devDependencies + Next's whole build
# toolchain, none of which belong in the image that actually runs in
# production. `output: "standalone"` (frontend/next.config.ts) traces only
# the files each page needs at runtime and copies them into
# .next/standalone -- combined with the deps/builder stages never reaching
# the final image, this keeps the runtime image to node_modules-free
# app code plus a minimal `next`-provided server.js, not the full
# node_modules tree `next start` would otherwise require.
#
# Node 22 matches this repo's own local dev/lockfile version (next's own
# package.json requires >=20.9.0; 22 is what this project actually
# developed and built against).

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Next.js inlines NEXT_PUBLIC_* variables into the client JS bundle at BUILD
# time, not read at container start -- the exact gotcha this project already
# hit once on Vercel (Spec.md: a scheme-less NEXT_PUBLIC_API_BASE_URL baked
# into a build required a full rebuild to fix, setting the env var alone did
# nothing). So this MUST be a build ARG passed via docker-compose's
# `build.args`, not a runtime `environment:` entry, or the deployed frontend
# will silently keep whatever URL (or none) it happened to build with.
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
# Un-rooted on purpose -- the standalone server.js needs no special
# privileges, and Next.js already ships a non-root `nextjs` user/group in
# its official Docker examples for exactly this reason.
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
