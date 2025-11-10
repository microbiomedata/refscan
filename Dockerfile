# ────────────────────────────────────────────────────────────────────────────┐
# This Dockerfile describes a container image that can be used to run refscan
# without installing Python or any Python packages.
# ────────────────────────────────────────────────────────────────────────────┘

FROM python:3.12-alpine

LABEL org.opencontainers.image.title="refscan"
LABEL org.opencontainers.image.description="Command-line program that scans the NMDC MongoDB database for referential integrity violations"
LABEL org.opencontainers.image.documentation="https://github.com/microbiomedata/refscan/README.md"
LABEL org.opencontainers.image.source="https://github.com/microbiomedata/refscan"
LABEL org.opencontainers.image.url="https://github.com/microbiomedata/refscan"

# Install `uv`.
WORKDIR /tmp
ADD https://astral.sh/uv/install.sh uv-installer.sh
RUN sh uv-installer.sh && rm uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

# Install production dependencies.
WORKDIR /code
COPY pyproject.toml pyproject.toml
COPY uv.lock        uv.lock
COPY README.md      README.md
RUN uv sync --no-dev --no-install-project --compile-bytecode --locked

# Install project (we do this after installing production dependencies
# so we can reuse those image layers if dependencies haven't changed).
WORKDIR /code
COPY refscan refscan
RUN uv sync --no-dev --compile-bytecode --locked

# Run refscan.
WORKDIR /code
ENTRYPOINT ["uv", "run", "--no-sync", "refscan"]
