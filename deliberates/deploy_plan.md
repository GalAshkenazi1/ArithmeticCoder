# Plan: the showcase online (for LinkedIn) and on mobile

## Status (2026-11-25)

Decided:
- **Host:** Hugging Face Spaces, Space `GalAshk/arithmetic-coder`.
- **App URL:** https://galashk-arithmetic-coder.hf.space
- **Repo:** public.
- **Version:** the full one, with GPT-2.

Done in the code (not yet committed):
- [x] **CPU-only torch on Linux:** `deploy/torch-cpu.toml`, which the Dockerfiles append to
      `pyproject.toml` before re-locking. It isn't in `pyproject.toml` itself because `training/`
      depends on the app and needs CUDA torch; uv can't hold both sources for the same package.
- [x] **Server settings:** `HOST`/`PORT` from the environment, startup warm-up (`ARITH_PRELOAD`), a
      response cache, a per-IP rate limit (`ARITH_RATE_LIMIT`), a 503 when the models stay busy
      (`ARITH_WAIT_SECONDS`), and `GET /api/health`. All covered by tests.
- [x] **Container:** `Dockerfile`, `.dockerignore`, and the Space's own files in
      `deploy/huggingface/`, plus `.github/workflows/deploy-space.yml` to redeploy on each tag.
- [x] **Checked on Linux** (WSL, without Docker):
  - the build steps work: CPU torch with no CUDA, GPT-2 downloads and converts, all 10 models
    preload (GPT-2 in 8 s)
  - every encoder round-trips through the running server
- [x] **GPT-2 measured on 2 cores**, as on the free tier:
  - 1.8–2.4 s to encode a sentence and about 1 s to decode it
  - 8 s to encode the 280-character maximum
  - each model has its own lock, so a slow GPT-2 request no longer stalls the small models: they
    answer in under 1 s instead of 7.7 s, with bit-identical results
  - so GPT-2 stays in
- [x] **Phone support:** taps open definitions, ladder boxes and chart tooltips; controls are at
      least 40 px on touch screens; the start page's animation stacks on narrow screens.
- [x] **Home-screen app (PWA):** manifest, icons, and a network-first service worker.
- [x] **README:** live-demo link, an animated GIF, four screenshots, and credits.

Left, all needing you:
1. **Release:** commit, merge `encoder-showcase` into `master`, tag `v1.0`, push.
2. **Make the GitHub repo public.**
3. **Create the Space** (Docker, CPU basic) and add the two files from `deploy/huggingface/`.
4. **Optional, for automatic redeploys:** add an `HF_TOKEN` (write) secret to the GitHub repo.

Goal: a public link anyone can open from a LinkedIn post, on a laptop or a phone, that runs the full
showcase (all four pages, GPT-2 included), plus a GitHub repo that looks good when people click
through.

## What we're deploying

- **Backend:** FastAPI + PyTorch on CPU (`uv run arith-demo`). It serves both the API and the static
  frontend from one process.
- **Models:** the small models are committed to git (9–21 MB each, about 110 MB in all). GPT-2's
  `ckpt.pt` (475 MB) is git-ignored and rebuilt by `training/fetch_gpt2.py`. That script only needs
  the app's own environment.
- **Memory:** small models need little; GPT-2 needs about 1 GB of RAM, and its first request takes
  seconds while it loads.
- **Speed:** small models encode in well under a second. GPT-2 does about 15 tokens a second on 2
  CPUs.

## Part 1: online

### Can a "git server" run it?

Only partly. GitHub hosts the code, and **GitHub Pages** can host the frontend. Pages serves static
files only, though, so it can't run the Python API and the models. Either the API runs on a host
that runs containers, or the models move into the browser (option C).

### Options

| | What it is | Cost | GPT-2? | Sleeps when idle | Effort |
|---|---|---|---|---|---|
| **A. Hugging Face Spaces (Docker)** | a container from a Dockerfile, public URL, built from a git repo | free tier (CPU basic: 2 vCPU, 16 GB RAM) | yes | after ~48 h without visitors (~1 min cold start) | ½–1 day |
| B. Render / Railway / Fly.io | the same container on a general host | free tiers are small (e.g. Render free: 512 MB, sleeps after 15 min) | not on free tiers | yes | ½–1 day |
| C. Static site + models in the browser | GitHub Pages; models run on the visitor's device (ONNX Runtime Web) | free | too heavy for phones | never | 1–2 weeks |

Check the free tiers' current limits before choosing: they change.

**Recommendation: A now, C later if you want.** Spaces is free, has enough RAM for GPT-2, is built
for ML demos, and is a link people on LinkedIn recognise. GitHub stays the source of truth; the
Space builds from it.

### Steps for option A

**0. Prepare the code** (a few small changes)

- [ ] **CPU-only torch on Linux.** In `pyproject.toml`, point `torch` at the PyTorch CPU index for
      Linux. This keeps the image around 1 GB instead of 4 GB+:
      ```toml
      [[tool.uv.index]]
      name = "pytorch-cpu"
      url = "https://download.pytorch.org/whl/cpu"
      explicit = true

      [tool.uv.sources]
      torch = [{ index = "pytorch-cpu", marker = "sys_platform == 'linux'" }]
      ```
      Then run `uv lock` and the tests again: the torch build changes the numbers, so check that
      encode → decode still round-trips.
- [ ] **Host and port from the environment.** `arith-demo` should also read `HOST` and `PORT`
      (Spaces uses 7860, other hosts set `$PORT`).
- [ ] **Warm-up at startup.** Load every model, GPT-2 included, when the server starts, so the
      first visitor doesn't wait for GPT-2.
- [ ] **Response cache.** Cache `(model, text)` → encode result. The examples everyone clicks then
      return instantly.
- [ ] **Basic protection for a public endpoint.**
  - one worker
  - the 280-character limit, already there
  - a small per-IP rate limit
  - a timeout on GPT-2 requests
  - `GET /api/health` for the host's health check
- [ ] **Release it.** Merge `encoder-showcase` into `master`, then tag a release (e.g. `v1.0`).

**1. Create the Space**

- [ ] **Create it:** huggingface.co → New Space → SDK "Docker" → public.
- [ ] **Space files:** the Space repo holds only two files, a `README.md` header and a
      `Dockerfile`. The Dockerfile clones the GitHub repo at the tag, so no model files need Git
      LFS on the Space side.
- [ ] **Private repo?** If the GitHub repo is private, add a read-only token as a Space secret and
      use it in the clone.

`README.md` (the Space's settings live in its header):

```yaml
---
title: Arithmetic Coding Showcase
emoji: 🗜️
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
---
Squeezing text into bits with language models and arithmetic coding.
Code: https://github.com/galashkenazi1/ArithmeticCoder
```

`Dockerfile`:

```dockerfile
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN useradd -m -u 1000 user          # Spaces run the container as user 1000
USER user
WORKDIR /home/user
ARG REF=v1.0                         # the GitHub tag to deploy
RUN git clone --depth 1 --branch ${REF} https://github.com/galashkenazi1/ArithmeticCoder app
WORKDIR /home/user/app
RUN uv sync --frozen --no-dev        # CPU-only torch (step 0)
RUN uv run python training/fetch_gpt2.py   # downloads ~550 MB and converts it into model_bank/gpt2/
EXPOSE 7860
CMD ["uv", "run", "--no-sync", "arith-demo", "--host", "0.0.0.0", "--port", "7860"]
```

**2. Keep it in sync**

- [ ] **Redeploy on each release:** a GitHub Action, triggered by a new tag, bumps `REF` in the
      Space's Dockerfile and pushes it to the Space, which rebuilds. It needs an HF write token as a
      GitHub secret.
- [ ] **Or by hand:** edit `REF` in the Space and save.

**3. Check it live**

- [ ] All four pages, the tour, GPT-2 (the first request after a cold start), and the receiver.
- [ ] Open the URL on a phone (Part 2).
- [ ] Ask two or three people to open it at the same time: is the GPT-2 queue acceptable?

### The GitHub repo, for visitors

- [ ] **README top:** a one-line pitch, a GIF of the start page and the coding animation, a
      **live demo** link to the Space, and 3 screenshots (start, encode, compare).
- [ ] **"How it works":** link to [model_families.md](model_families.md) and the studies.
- [ ] **Licence and credits:**
  - a licence for the code (e.g. MIT)
  - GPT-2 (MIT, OpenAI)
  - each training corpus's licence: Tiny Shakespeare and Gutenberg are public domain, WikiText is
    CC BY-SA, TinyStories is CDLA-Sharing, C4 is ODC-BY. Check each before listing it.
- [ ] Pin the repo on your GitHub profile.

### The LinkedIn post

- [ ] **Video first.** A 30–60 s screen recording, which LinkedIn autoplays: the start page's
      "Word in 12 bits" animation, then the Encode page, then Compare (GPT-2 against the
      Shakespearian Encoder on Hamlet).
- [ ] **Text:** a hook ("I compressed Shakespeare to 2 bits per letter with a 1M-parameter model"),
      three short bullets on what's interesting, then the live link and the GitHub link.
- [ ] **Wake the Space up shortly before posting.** Free Spaces sleep, and the first visitor would
      wait a minute.

## Part 2: on mobile

### Level 1: the website in a phone's browser (needed for LinkedIn anyway)

Most LinkedIn traffic is on phones. The pages already fit a 420 px screen with no sideways scrolling,
but some interactions only work with a mouse:

- [ ] **Touch for the chart tooltips:** on the Encode graph and both Compare charts, use pointer
      events: tap to show, tap elsewhere to hide.
- [ ] **Tap for the dotted words:** today their definitions open on hover and keyboard focus;
      a tap should open them too.
- [ ] **The ladder's boxes:** their probabilities are in SVG `<title>`s, which phones don't show.
      Tapping a box should show its "1 in N → cost".
- [ ] **Tap targets of at least 40 px:** the playback and speed buttons are 30–32 px now.
- [ ] **The start page's "Word" animation:** it scales down to small text on a phone. Add a stacked
      layout below about 560 px: text, then model, then probabilities, then range.
- [ ] **Test on real phones before the deploy:**
  1. Run `uv run arith-demo --host 0.0.0.0` on the PC.
  2. Open `http://<PC's IP>:8000` on a phone on the same Wi-Fi, allowing the Windows firewall
     prompt.
  3. Test iOS Safari and Android Chrome.

### Level 2: "install" it (a PWA)

- [ ] **A web manifest:** name, icons, theme colour and `display: standalone`, so "Add to Home
      Screen" makes an app icon that opens full-screen.
- [ ] **A service worker** that caches the static frontend, so the app opens instantly. Encoding
      still needs the server; show a clear "offline" message when it's unreachable.

### Level 3 (optional): fully on the phone, no server

This is option C from Part 1. It's the most impressive version and costs nothing to host.

- [ ] **Models in the browser:** export the small nanoGPT models to ONNX (`torch.onnx.export`) and
      run them with ONNX Runtime Web (WebAssembly, or WebGPU where available).
- [ ] **The coder in JavaScript:**
  - the integer CDF quantisation and the interval arithmetic with `BigInt`
  - the char, byte and word tokenizers (GPT-2's BPE can be ported later)
- [ ] **Leave GPT-2 out on phones.** Its 475 MB is too much to download, and even a quantised
      version is heavy. Keep it on the server version.
- [ ] **Caveat:** browser maths isn't bit-identical to PyTorch, so an in-browser encoding may not
      decode on the server. That's fine for a showcase where encode and decode both happen on the
      same device.

### Level 4 (not needed for LinkedIn): an app-store app

Wrap the PWA with Capacitor for iOS and Android. That needs developer accounts and review, which a
portfolio piece doesn't need.

## Order and effort

| Phase | What | Effort |
|---|---|---|
| 0 | code prep (CPU torch, PORT, warm-up, cache, rate limit), merge, tag | ½ day |
| 1 | the Space live, synced from GitHub | ½–1 day |
| 2 | mobile polish (touch, tap targets, stacked animation) + PWA | 1–2 days |
| 3 | README polish, GIF, video, LinkedIn post | ½ day |
| 4 (optional) | models in the browser, GitHub Pages, offline | 1–2 weeks |

## Decisions for you

1. **Is the GitHub repo public?** A public repo is better for LinkedIn, and simpler for the Space
   to build from.
2. **Hugging Face account name:** the Space URL will be `huggingface.co/spaces/<name>/<space>`.
3. **GPT-2 on the free tier, or not?** Yes on Spaces. If you ever move to a small host, the registry
   already lists GPT-2 as "files missing" when `ckpt.pt` isn't there, and everything else keeps
   working.
4. **Level 3?** In-browser models would be a strong "how I built it" story, but it's a much bigger
   job.
