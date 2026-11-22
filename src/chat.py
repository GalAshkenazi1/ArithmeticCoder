"""Command-line chat client: arithmetic-coded messages to peers through the relay.

Run:  python -m src.chat --user alice [--relay ws://127.0.0.1:8765] [--state-dir DIR]

ChatController holds all the logic and reports through an `output(line)` callback, so it can be
tested without a terminal; main() only adds the prompt_toolkit input line on top.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from src.client import CorruptedPayloadError, ModelMismatchError, UserClient
from src.encdec import MessagePack
from src.model_bank import MODEL_NAMES, ModelBankError, load_model
from src.peer_store import load_peers, save_peers, state_path
from src.protocol import check_id, decode_control, encode_control, pack_routed, unpack_routed

DEFAULT_RELAY = "ws://127.0.0.1:8765"
PENDING, VERIFIED, MISMATCH = "pending", "verified", "MISMATCH"

HELP = """commands:
  /add <peer> <model> <key> [precision]   connect to a peer (both sides must use the same model + key)
  /to <peer>                              send plain lines to this peer
  /peers                                  list peers, their model and handshake status
  /models                                 list available models
  /stats on|off                           show encoded sizes
  /remove <peer>                          forget a peer
  /help, /quit
anything else is sent to the current peer. keys have no spaces and are saved in plain text (POC)."""


class ChatError(RuntimeError):
    """Raised when the client can't join the relay (e.g. the user id is already online)."""


def _sizes(text: str, frame: bytes) -> str:
    """Describe a message's encoded size, e.g. '(32 chars -> 16 B, 2.59 bits/char)'."""
    _, pack = MessagePack.from_bytes(frame)
    k = pack.r.denominator.bit_length() - 1
    bpc = f", {k / len(text):.2f} bits/char" if text else ""
    return f"({len(text)} chars -> {len(frame)} B{bpc})"


class ChatController:
    """One user's chat logic: peers, handshakes, sending and receiving through the relay."""

    def __init__(self, user_id: str, relay_url: str = DEFAULT_RELAY, state_dir: Path | None = None,
                 output: Callable[[str], None] = print):
        """Set up an offline controller; call start() to connect."""
        check_id(user_id)
        self.user_id = user_id
        self.relay_url = relay_url
        self.output = output
        self.client = UserClient(user_id)
        self.store_path = state_path(user_id, state_dir)
        self.peers: dict[str, dict] = {}            # saved config per registered peer
        self.status: dict[str, str] = {}            # handshake status per registered peer
        self.offered: dict[str, str] = {}           # fingerprints from peers we haven't added yet
        self.held: defaultdict[str, list[bytes]] = defaultdict(list)  # their frames, decoded after /add
        self.current: str | None = None
        self.show_stats = False
        self.connected = False
        self._ws: ClientConnection | None = None
        self._codec_lock = asyncio.Lock()           # one encode/decode at a time
        self._receiver: asyncio.Task | None = None

    # ---- connection -------------------------------------------------------------------------

    async def start(self) -> None:
        """Connect, say hello, restore saved peers (re-handshaking each), then start receiving."""
        self._ws = await connect(self.relay_url)
        await self._ws.send(encode_control({"type": "hello", "user": self.user_id}))
        reply = decode_control(await self._ws.recv())
        if reply["type"] != "welcome":
            await self._ws.close()
            raise ChatError(reply.get("message", f"unexpected reply {reply['type']!r}"))
        self.connected = True
        # restore before reading anything, so queued messages find their sessions
        for peer_id, config in load_peers(self.store_path).items():
            try:
                await self._register(peer_id, config, save=False)
            except (ModelBankError, ValueError) as e:
                self.output(f"[!] could not restore {peer_id}: {e}")
        if self.peers:
            self.output(f"restored peers: {', '.join(self.peers)}")
        self._receiver = asyncio.create_task(self._receive_loop())

    async def close(self) -> None:
        """Stop receiving and close the connection."""
        if self._receiver:
            self._receiver.cancel()
        if self._ws:
            await self._ws.close()
        self.connected = False

    async def _receive_loop(self) -> None:
        """Handle everything the relay sends until the connection closes."""
        try:
            async for message in self._ws:
                try:
                    await self._on_message(message)
                except Exception as e:  # one bad message must never kill the client
                    self.output(f"[!] error handling a message: {e}")
        except ConnectionClosed:
            pass
        self.connected = False
        self.output("[!] disconnected from the relay; restart to reconnect")

    async def _on_message(self, message: bytes | str) -> None:
        """Dispatch one relay message: a chat frame (bytes) or a control message (JSON text)."""
        if isinstance(message, bytes):
            sender, frame = unpack_routed(message)
            await self._on_frame(sender, frame)
            return
        control = decode_control(message)
        if control["type"] == "handshake":
            await self._on_handshake(control["from"], control["fingerprint"], control.get("reply", False))
        elif control["type"] == "error":
            self.output(f"[!] relay: {control.get('message')}")

    # ---- handshakes -------------------------------------------------------------------------

    async def _send_handshake(self, peer_id: str, reply: bool) -> None:
        """Send our fingerprint for the session with peer_id."""
        fingerprint = self.client.sessions[peer_id].fingerprint.hex()
        await self._ws.send(encode_control({"type": "handshake", "to": peer_id,
                                            "fingerprint": fingerprint, "reply": reply}))

    def _set_status(self, peer_id: str, peer_fingerprint_hex: str) -> None:
        """Compare the peer's fingerprint with ours and report any change."""
        try:
            ok = self.client.verify_peer_handshake(peer_id, bytes.fromhex(peer_fingerprint_hex))
        except ValueError:
            ok = False
        new = VERIFIED if ok else MISMATCH
        if self.status.get(peer_id) != new:
            self.status[peer_id] = new
            if ok:
                self.output(f"* {peer_id}: handshake verified (same model and key)")
            else:
                self.output(f"[!] {peer_id}: handshake MISMATCH - you and {peer_id} use a different model, key "
                            f"or precision; messages won't decode")

    async def _on_handshake(self, sender: str, fingerprint_hex: str, reply: bool) -> None:
        """Verify a peer's fingerprint; answer it unless it is itself an answer (so it can't loop)."""
        if sender in self.client.sessions:
            self._set_status(sender, fingerprint_hex)
            if not reply:
                await self._send_handshake(sender, reply=True)
        elif not reply:
            self.offered[sender] = fingerprint_hex
            self.output(f"* {sender} wants to chat (fingerprint {fingerprint_hex}) - "
                        f"/add {sender} <model> <key> to accept")

    # ---- peers ------------------------------------------------------------------------------

    async def _register(self, peer_id: str, config: dict, save: bool = True) -> None:
        """Create the session for peer_id, handshake, and decode anything they sent before."""
        model = await asyncio.to_thread(load_model, config["model"])
        self.client.register_peer(peer_id, model, config["key"], config["precision_bits"])
        self.peers[peer_id] = config
        self.status[peer_id] = PENDING
        if save:
            save_peers(self.store_path, self.peers)
        if self.current is None:
            self.current = peer_id
        await self._send_handshake(peer_id, reply=False)
        if peer_id in self.offered:
            self._set_status(peer_id, self.offered.pop(peer_id))
        for frame in self.held.pop(peer_id, []):
            await self._decode_and_show(peer_id, frame)

    # ---- messages ---------------------------------------------------------------------------

    async def _on_frame(self, sender: str, frame: bytes) -> None:
        """Show a received chat frame, or hold it until the sender is added."""
        if sender in self.client.sessions:
            await self._decode_and_show(sender, frame)
            return
        self.held[sender].append(frame)
        if len(self.held[sender]) == 1:
            self.output(f"* message from {sender} held - /add {sender} <model> <key> to read it")

    async def _decode_and_show(self, sender: str, frame: bytes) -> None:
        """Decode a frame from sender and print it (or a warning if it can't be decoded)."""
        try:
            async with self._codec_lock:
                result = await asyncio.to_thread(self.client.receive_from, sender, frame)
        except ModelMismatchError:
            self.output(f"[!] message from {sender} can't be decoded: model/key mismatch (see /peers)")
            return
        except CorruptedPayloadError as e:
            self.output(f"[!] corrupted message from {sender}: {e}")
            return
        stats = f"   {_sizes(result.text, frame)}" if self.show_stats else ""
        self.output(f"[{sender}] {result.text}{stats}")

    async def send(self, text: str) -> None:
        """Encode text for the current peer and send it through the relay."""
        peer = self.current
        if peer is None:
            self.output("[!] no current peer - /add one, or pick one with /to")
            return
        coder = self.client.sessions[peer].coder
        unknown = sorted({c for c in text if c not in coder.char_to_idx})
        if unknown:
            self.output(f"[!] not sent: {' '.join(repr(c) for c in unknown)} not in the model's vocabulary")
            return
        if not self.connected:
            self.output("[!] not sent: not connected to the relay")
            return
        async with self._codec_lock:
            frame = await asyncio.to_thread(self.client.send_to, peer, text)
        await self._ws.send(pack_routed(peer, frame))
        if self.show_stats:
            self.output(f"  -> {peer} {_sizes(text, frame)}")

    # ---- commands ---------------------------------------------------------------------------

    def prompt(self) -> str:
        """Prompt text showing who plain lines go to, e.g. 'alice->bob> '."""
        return f"{self.user_id}->{self.current or '?'}> "

    async def handle_line(self, line: str) -> bool:
        """Run one input line (command or message); return False when the user wants to quit."""
        line = line.strip()
        if not line:
            return True
        if not line.startswith("/"):
            await self.send(line)
            return True
        command, *args = line.split()
        handler = {
            "/add": self._cmd_add, "/to": self._cmd_to, "/peers": self._cmd_peers,
            "/models": self._cmd_models, "/stats": self._cmd_stats, "/remove": self._cmd_remove,
            "/help": self._cmd_help,
        }.get(command)
        if command == "/quit":
            return False
        if handler is None:
            self.output(f"[!] unknown command {command} - try /help")
            return True
        try:
            await handler(args)
        except (ValueError, ModelBankError) as e:
            self.output(f"[!] {e}")
        return True

    async def _cmd_add(self, args: list[str]) -> None:
        """/add <peer> <model> <key> [precision]"""
        if len(args) not in (3, 4):
            raise ValueError("usage: /add <peer> <model> <key> [precision]")
        peer, model, key = args[:3]
        precision = int(args[3]) if len(args) == 4 else 16
        check_id(peer)
        if peer == self.user_id:
            raise ValueError("you can't add yourself")
        if peer in self.client.sessions:
            raise ValueError(f"{peer} is already added; /remove {peer} first to change it")
        if model not in MODEL_NAMES:
            raise ValueError(f"unknown model {model!r}; choose from {', '.join(MODEL_NAMES)}")
        if not 8 <= precision <= 32:
            raise ValueError("precision must be between 8 and 32")
        await self._register(peer, {"model": model, "key": key, "precision_bits": precision})
        self.output(f"* added {peer} ({model}); waiting for their handshake")

    async def _cmd_to(self, args: list[str]) -> None:
        """/to <peer>"""
        if len(args) != 1 or args[0] not in self.client.sessions:
            raise ValueError(f"usage: /to <peer>, one of: {', '.join(self.client.sessions) or '(none yet)'}")
        self.current = args[0]

    async def _cmd_peers(self, args: list[str]) -> None:
        """/peers"""
        if not self.peers and not self.offered:
            self.output("no peers yet - /add <peer> <model> <key>")
        for peer, config in self.peers.items():
            mark = "*" if peer == self.current else " "
            fingerprint = self.client.sessions[peer].fingerprint.hex()
            self.output(f"{mark} {peer:12s} {config['model']:17s} {self.status[peer]:9s} fingerprint {fingerprint}")
        for peer, fingerprint in self.offered.items():
            self.output(f"  {peer:12s} {'(not added)':17s} {'offered':9s} fingerprint {fingerprint}")

    async def _cmd_models(self, args: list[str]) -> None:
        """/models"""
        self.output("models: " + ", ".join(MODEL_NAMES))

    async def _cmd_stats(self, args: list[str]) -> None:
        """/stats on|off"""
        if args not in (["on"], ["off"]):
            raise ValueError("usage: /stats on|off")
        self.show_stats = args == ["on"]
        self.output(f"stats {args[0]}")

    async def _cmd_remove(self, args: list[str]) -> None:
        """/remove <peer>"""
        if len(args) != 1 or args[0] not in self.client.sessions:
            raise ValueError("usage: /remove <peer>")
        peer = args[0]
        self.client.remove_peer(peer)
        del self.peers[peer], self.status[peer]
        save_peers(self.store_path, self.peers)
        if self.current == peer:
            self.current = next(iter(self.peers), None)
        self.output(f"* removed {peer}")

    async def _cmd_help(self, args: list[str]) -> None:
        """/help"""
        self.output(HELP)


async def run_cli(user: str, relay: str, state_dir: Path | None) -> int:
    """Run the interactive client until /quit, Ctrl-C or Ctrl-D."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.patch_stdout import patch_stdout

    controller = ChatController(user, relay, state_dir, output=print)
    with patch_stdout():  # incoming lines print above the input line
        try:
            await controller.start()
        except (OSError, ChatError, ConnectionClosed) as e:
            print(f"could not join the relay at {relay}: {e}")
            return 1
        print(f"connected to {relay} as {user!r} - /help for commands")
        session = PromptSession()
        while True:
            try:
                line = await session.prompt_async(controller.prompt)
            except (EOFError, KeyboardInterrupt):
                break
            try:
                if not await controller.handle_line(line):
                    break
            except ConnectionClosed:
                print("[!] not sent: the relay connection is closed")
        await controller.close()
    return 0


def main() -> None:
    """Parse arguments and start the interactive client."""
    parser = argparse.ArgumentParser(description="Arithmetic-coding chat client.")
    parser.add_argument("--user", required=True, help="your user id (no spaces)")
    parser.add_argument("--relay", default=DEFAULT_RELAY, help=f"relay URL (default {DEFAULT_RELAY})")
    parser.add_argument("--state-dir", type=Path, default=None, help="where peers are saved (default ~/.arithmetic_chat)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run_cli(args.user, args.relay, args.state_dir)))


if __name__ == "__main__":
    main()
