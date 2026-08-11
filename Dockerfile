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

WORKDIR /app

# System build tools are NOT installed -- every wheel needed is prebuilt for
# this platform (see above); if a future dependency ever needs to compile
# from source, pip's error will say so explicitly and gcc/etc. can be added
# then, rather than carrying them unconditionally.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# No --reload (dev-only, watches the filesystem and restarts on every
# change -- wasted overhead in a container that's rebuilt on every deploy
# anyway, not restarted in place).
CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000"]
