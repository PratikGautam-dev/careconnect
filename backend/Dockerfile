# Backend (FastAPI) production image -- Section 15's move off Railway onto a
# self-hosted DigitalOcean VPS (behind Coolify, which handles the reverse
# proxy/TLS itself -- see docker-compose.yml/DEPLOYMENT.md, nothing in this
# image or compose file does that job).
#
# Single stage, deliberately: this app has no compiled build step of its own
# (no TypeScript, no bundling) and its two heaviest dependencies
# (psycopg2-binary, cryptography via Authlib) both ship prebuilt manylinux
# wheels for this base image, so there's nothing a build stage would
# discard that `pip install` doesn't already avoid pulling in -- a
# builder/runtime split here would add complexity without shrinking the
# image. Contrast with frontend/Dockerfile, where Next.js's node_modules
# (dev deps + the whole build toolchain) genuinely don't belong in the
# runtime image, which is why that one IS multi-stage.
FROM python:3.12-slim

# uv binary, copied straight from Astral's distroless image rather than
# pip-installed -- avoids needing pip itself in the final image just to
# bootstrap uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# System build tools are NOT installed -- every wheel needed is prebuilt for
# this platform (see above); if a future dependency ever needs to compile
# from source, uv's error will say so explicitly and gcc/etc. can be added
# then, rather than carrying them unconditionally.
COPY pyproject.toml uv.lock ./
# --locked: fail the build rather than silently drift if uv.lock is ever out
# of sync with pyproject.toml. --no-dev: pytest/testcontainers etc. never
# belong in the production image.
RUN uv sync --locked --no-dev

COPY . .

EXPOSE 8000

# No --reload (dev-only, watches the filesystem and restarts on every
# change -- wasted overhead in a container that's rebuilt on every deploy
# anyway, not restarted in place).
# --proxy-headers/--forwarded-allow-ips: this container always sits behind
# a reverse proxy (Coolify's Traefik, or Nginx per DEPLOYMENT.md) that
# terminates TLS and forwards plain HTTP internally -- without trusting
# X-Forwarded-Proto, Starlette's request.url_for() (used by
# user_auth.py's Google OAuth redirect_uri) builds an http:// URL even
# though the real request was https://, which Google rejects as
# redirect_uri_mismatch (a real incident on Railway, same underlying
# cause -- see Spec.md Section 0 and railway.toml's own startCommand).
CMD ["uv", "run", "--no-sync", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
