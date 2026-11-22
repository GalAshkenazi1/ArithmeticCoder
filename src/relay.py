"""Zero-knowledge relay: routes chat frames and handshakes between users by id, queues for offline users.

Run:  python -m src.relay [--host 127.0.0.1] [--port 8765]

The relay never loads a model or sees a key; it only reads user ids and forwards opaque bytes.
"""
import argparse
import asyncio
import logging
from collections import defaultdict, deque

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from src.protocol import check_id, decode_control, encode_control, pack_routed, unpack_routed

log = logging.getLogger("relay")

QUEUE_LIMIT = 200   # undelivered messages kept per offline user (oldest dropped first)
HELLO_TIMEOUT = 10  # seconds a new connection has to identify itself


class Relay:
    """Routing state: who is online, and what is waiting for whom."""

    def __init__(self, queue_limit: int = QUEUE_LIMIT):
        """Start with nobody online and empty queues."""
        self.online: dict[str, ServerConnection] = {}
        self.flushing: set[str] = set()  # users whose queue is still being delivered (keeps order)
        self.queues: defaultdict[str, deque] = defaultdict(lambda: deque(maxlen=queue_limit))

    async def handler(self, ws: ServerConnection) -> None:
        """Serve one client connection: hello, then forward everything it sends."""
        user = await self._hello(ws)
        if user is None:
            return
        try:
            async for message in ws:
                try:
                    await self._route(user, message)
                except (ValueError, KeyError, TypeError) as e:
                    await ws.send(encode_control({"type": "error", "message": f"malformed message: {e}"}))
        except ConnectionClosed:
            pass
        finally:
            if self.online.get(user) is ws:
                del self.online[user]
            log.info("disconnect %s", user)

    async def _hello(self, ws: ServerConnection) -> str | None:
        """Read the client's hello, reject duplicates, then deliver its queued messages in order."""
        try:
            hello = decode_control(await asyncio.wait_for(ws.recv(), HELLO_TIMEOUT))
            if hello["type"] != "hello":
                raise ValueError("first message must be hello")
            user = hello["user"]
            check_id(user)
        except (asyncio.TimeoutError, ValueError, KeyError, TypeError, ConnectionClosed) as e:
            await self._send_error_and_close(ws, f"bad hello: {e}")
            return None
        if user in self.online:
            await self._send_error_and_close(ws, f"user {user!r} is already online")
            return None

        self.online[user] = ws
        self.flushing.add(user)
        try:
            await ws.send(encode_control({"type": "welcome"}))
            queue = self.queues.pop(user, deque())
            log.info("connect %s (%d queued)", user, len(queue))
            while queue:  # messages arriving meanwhile are queued again, so order is kept
                await ws.send(queue.popleft())
                queue.extend(self.queues.pop(user, ()))
        finally:
            self.flushing.discard(user)
        return user

    async def _route(self, sender: str, message: bytes | str) -> None:
        """Rewrite one message's address from recipient to sender and deliver it."""
        if isinstance(message, bytes):
            recipient, frame = unpack_routed(message)
            await self._deliver(recipient, pack_routed(sender, frame))
            log.info("route %s -> %s (%d B frame)", sender, recipient, len(frame))
            return
        control = decode_control(message)
        if control["type"] != "handshake":
            raise ValueError(f"unexpected control type {control['type']!r}")
        recipient = control["to"]
        check_id(recipient)
        await self._deliver(recipient, encode_control({
            "type": "handshake",
            "from": sender,
            "fingerprint": str(control["fingerprint"]),
            "reply": bool(control.get("reply", False)),
        }))
        log.info("handshake %s -> %s", sender, recipient)

    async def _deliver(self, recipient: str, message: bytes | str) -> None:
        """Send to the recipient if online (and not mid-flush), otherwise queue it."""
        ws = self.online.get(recipient)
        if ws is not None and recipient not in self.flushing:
            try:
                await ws.send(message)
                return
            except ConnectionClosed:
                pass
        self.queues[recipient].append(message)
        log.info("queued for %s (%d waiting)", recipient, len(self.queues[recipient]))

    @staticmethod
    async def _send_error_and_close(ws: ServerConnection, message: str) -> None:
        """Tell the client what went wrong, then close its connection."""
        try:
            await ws.send(encode_control({"type": "error", "message": message}))
            await ws.close()
        except ConnectionClosed:
            pass


async def start_relay(host: str = "127.0.0.1", port: int = 8765) -> Server:
    """Start a relay and return the running server (port 0 picks a free port; see server.sockets)."""
    return await serve(Relay().handler, host, port)


async def _main(host: str, port: int) -> None:
    """Run the relay until interrupted."""
    server = await start_relay(host, port)
    log.info("relay listening on ws://%s:%d", host, port)
    await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zero-knowledge relay for the arithmetic-coding chat.")
    parser.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to accept LAN connections")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    try:
        asyncio.run(_main(args.host, args.port))
    except KeyboardInterrupt:
        pass
