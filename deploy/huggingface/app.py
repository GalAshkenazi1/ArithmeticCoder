"""The Hugging Face Space's entry point.

The Space uses the Gradio SDK, which installs requirements.txt and runs `python app.py`. This file
then serves the showcase's own FastAPI app on port 7860; Gradio is installed but not used.

At start-up it:
1. downloads the tagged source from GitHub: the code, the small trained models and the web pages;
2. installs GPT-2 into the model bank with training/fetch_gpt2.py (a ~550 MB download from Hugging Face);
3. loads every encoder and serves the API and the pages.

A free Space forgets its disk when it sleeps, so waking up repeats these steps (a minute or two).
To serve another tag or branch, set the Space variable ARITH_REF.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

REPO = "https://github.com/GalAshkenazi1/ArithmeticCoder"
DEFAULT_REF = "v1.0"  # the deploy workflow rewrites this line to the tag it deploys
REF = os.environ.get("ARITH_REF", DEFAULT_REF)
SOURCE_URL = os.environ.get("ARITH_SOURCE_URL", f"{REPO}/archive/{REF}.tar.gz")
HERE = Path(__file__).resolve().parent
ROOT = HERE / "source"  # the unpacked repository


def fetch_source() -> None:
    """Download the repository at REF and unpack it into ROOT."""
    stamp = ROOT / ".source-url"
    if stamp.exists() and stamp.read_text() == SOURCE_URL:
        return
    print(f"downloading {SOURCE_URL}", flush=True)
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "arithmetic-coder-space"})
    with urllib.request.urlopen(request) as response:
        data = response.read()
    print(f"unpacking {len(data) / 1e6:.0f} MB", flush=True)
    unpacked = HERE / "source.part"
    for folder in (ROOT, unpacked):
        shutil.rmtree(folder, ignore_errors=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(unpacked, filter="data")
    (top,) = unpacked.iterdir()  # GitHub puts everything in one folder, e.g. ArithmeticCoder-1.0/
    top.rename(ROOT)
    unpacked.rmdir()
    stamp.write_text(SOURCE_URL)


def install_gpt2() -> None:
    """Install GPT-2 into the model bank. If that fails, the app still serves the other encoders."""
    if (ROOT / "model_bank" / "gpt2" / "ckpt.pt").exists():
        return
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    try:
        subprocess.run([sys.executable, "training/fetch_gpt2.py"], cwd=ROOT, env=env, check=True)
    except subprocess.CalledProcessError as error:
        print(f"GPT-2 could not be installed ({error}); serving the other encoders", flush=True)
    finally:
        shutil.rmtree(ROOT / "training" / "_downloads", ignore_errors=True)


def serve() -> None:
    """Run the showcase server (the repository's arith-demo) from the unpacked source."""
    os.environ.update(HOST="0.0.0.0", PORT=os.environ.get("GRADIO_SERVER_PORT", "7860"))
    for name, value in {"ARITH_PRELOAD": "all", "ARITH_RATE_LIMIT": "120", "ARITH_WAIT_SECONDS": "45"}.items():
        os.environ.setdefault(name, value)
    sys.path.insert(0, str(ROOT / "src"))
    from arithmetic_coder.api.app import main

    sys.argv = sys.argv[:1]
    main()


if __name__ == "__main__":
    fetch_source()
    install_gpt2()
    serve()
