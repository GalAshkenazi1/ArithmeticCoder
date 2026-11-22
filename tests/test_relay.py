"""Tests for the relay, using raw websocket clients against an in-process relay on a free port."""
import asyncio

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from src.protocol import decode_control, encode_control, pack_routed, unpack_routed
from src.relay import start_relay


async def relay_url():
    """Start a relay on a free port; return (server, url)."""
    server = await start_relay("127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://127.0.0.1:{port}"


async def join(url, user):
    """Connect and say hello; return the connection after the welcome."""
    ws = await connect(url)
    await ws.send(encode_control({"type": "hello", "user": user}))
    assert decode_control(await ws.recv()) == {"type": "welcome"}
    return ws


async def recv(ws, timeout=5):
    """Receive one message or fail the test after a timeout."""
    return await asyncio.wait_for(ws.recv(), timeout)


def test_routes_frames_and_rewrites_sender():
    async def scenario():
        server, url = await relay_url()
        alice, bob = await join(url, "alice"), await join(url, "bob")
        await alice.send(pack_routed("bob", b"\x01\x02frame"))
        assert unpack_routed(await recv(bob)) == ("alice", b"\x01\x02frame")
        await bob.send(pack_routed("alice", b"back"))
        assert unpack_routed(await recv(alice)) == ("bob", b"back")
        server.close()
    asyncio.run(scenario())


def test_routes_handshakes():
    async def scenario():
        server, url = await relay_url()
        alice, bob = await join(url, "alice"), await join(url, "bob")
        await alice.send(encode_control({"type": "handshake", "to": "bob", "fingerprint": "abcd0123", "reply": False}))
        assert decode_control(await recv(bob)) == {
            "type": "handshake", "from": "alice", "fingerprint": "abcd0123", "reply": False}
        server.close()
    asyncio.run(scenario())


def test_queues_for_offline_user_in_order():
    async def scenario():
        server, url = await relay_url()
        alice = await join(url, "alice")
        await alice.send(encode_control({"type": "handshake", "to": "carol", "fingerprint": "00", "reply": False}))
        for i in range(3):
            await alice.send(pack_routed("carol", bytes([i])))
        await asyncio.sleep(0.1)
        carol = await join(url, "carol")
        assert decode_control(await recv(carol))["type"] == "handshake"
        assert [unpack_routed(await recv(carol)) for _ in range(3)] == [("alice", bytes([i])) for i in range(3)]
        server.close()
    asyncio.run(scenario())


def test_rejects_duplicate_user_and_bad_hello():
    async def scenario():
        server, url = await relay_url()
        await join(url, "alice")
        dup = await connect(url)
        await dup.send(encode_control({"type": "hello", "user": "alice"}))
        assert "already online" in decode_control(await recv(dup))["message"]
        bad = await connect(url)
        await bad.send(b"\x03bob frame before hello")
        assert decode_control(await recv(bad))["type"] == "error"
        for ws in (dup, bad):
            try:
                await recv(ws)
                raise AssertionError("connection should be closed")
            except ConnectionClosed:
                pass
        server.close()
    asyncio.run(scenario())


def test_malformed_message_keeps_connection_open():
    async def scenario():
        server, url = await relay_url()
        alice, bob = await join(url, "alice"), await join(url, "bob")
        await alice.send(b"\x00")
        assert decode_control(await recv(alice))["type"] == "error"
        await alice.send(pack_routed("bob", b"still works"))
        assert unpack_routed(await recv(bob)) == ("alice", b"still works")
        server.close()
    asyncio.run(scenario())
