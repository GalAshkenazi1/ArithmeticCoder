# The encoder showcase as one container: the API, the frontend and every model, GPT-2 included.
#
#   docker build -t arithmetic-coder .
#   docker run -p 7860:7860 arithmetic-coder          then open http://localhost:7860
#
# The Hugging Face Space builds the same thing from a GitHub tag (deploy/huggingface/Dockerfile).
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never
WORKDIR /home/user/app

# dependencies first, so code changes don't reinstall them. deploy/torch-cpu.toml switches torch to
# its CPU-only build on Linux (uv re-locks; every other version stays as pinned in uv.lock).
COPY --chown=user pyproject.toml uv.lock ./
COPY --chown=user deploy/torch-cpu.toml deploy/
RUN cat deploy/torch-cpu.toml >> pyproject.toml && uv lock && uv sync --frozen --no-dev --no-install-project

COPY --chown=user . .
# the copy brought back the original pyproject.toml and uv.lock: switch torch to the CPU build again
RUN cat deploy/torch-cpu.toml >> pyproject.toml && uv lock && uv sync --frozen --no-dev
# GPT-2 isn't in git (475 MB): download it from Hugging Face, convert it, and drop the download
RUN uv run --no-sync python training/fetch_gpt2.py && rm -rf training/_downloads

# public-server settings (see src/arithmetic_coder/api/app.py)
ENV HOST=0.0.0.0 PORT=7860 ARITH_PRELOAD=all ARITH_RATE_LIMIT=120 ARITH_WAIT_SECONDS=45
EXPOSE 7860
CMD ["uv", "run", "--no-sync", "arith-demo"]
