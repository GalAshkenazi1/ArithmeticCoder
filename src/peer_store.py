"""Remember a user's peers (model, key, precision) between runs, in a JSON file outside the repo.

Keys are stored in plain text: fine for this proof of concept, not for real secrets.
"""
import json
import os
from pathlib import Path

DEFAULT_STATE_DIR = Path.home() / ".arithmetic_chat"


def state_path(user_id: str, state_dir: Path | None = None) -> Path:
    """Return the JSON file that holds user_id's peers."""
    return Path(state_dir or DEFAULT_STATE_DIR) / f"{user_id}.json"


def load_peers(path: Path) -> dict[str, dict]:
    """Return {peer_id: {"model", "key", "precision_bits"}}, or {} if the file doesn't exist yet."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("peers", {})


def save_peers(path: Path, peers: dict[str, dict]) -> None:
    """Write the peers atomically (temp file + rename), so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"peers": peers}, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
