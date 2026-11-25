# The Hugging Face Space's Dockerfile: it builds the showcase from a GitHub tag, so the Space repo
# holds only this file and README.md (no model files, no Git LFS). The GitHub Action in
# .github/workflows/deploy-space.yml sets REF to each new tag and pushes this file to the Space.
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never

ARG REF=v1.0
RUN git clone --depth 1 --branch ${REF} https://github.com/GalAshkenazi1/ArithmeticCoder /home/user/app
WORKDIR /home/user/app
# torch's CPU-only build on Linux (see deploy/torch-cpu.toml); every other version stays as pinned
RUN cat deploy/torch-cpu.toml >> pyproject.toml && uv lock && uv sync --frozen --no-dev
# GPT-2 isn't in git (475 MB): download it from Hugging Face, convert it, and drop the download
RUN uv run --no-sync python training/fetch_gpt2.py && rm -rf training/_downloads

ENV HOST=0.0.0.0 PORT=7860 ARITH_PRELOAD=all ARITH_RATE_LIMIT=120 ARITH_WAIT_SECONDS=45
EXPOSE 7860
CMD ["uv", "run", "--no-sync", "arith-demo"]
