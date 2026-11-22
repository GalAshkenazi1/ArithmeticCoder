"""End-to-end: two ChatControllers talking through an in-process relay (no terminal needed)."""
import asyncio

import pytest

from src.chat import MISMATCH, VERIFIED, ChatController, ChatError, run_cli
from src.relay import start_relay


async def start_relay_url():
    """Start a relay on a free port; return (server, url)."""
    server = await start_relay("127.0.0.1", 0)
    return server, f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"


async def make_user(user, url, state_dir):
    """Start a controller whose output goes into a list; retry briefly if the relay still sees the old login."""
    out: list[str] = []
    for _ in range(50):
        controller = ChatController(user, url, state_dir, output=out.append)
        try:
            await controller.start()
            return controller, out
        except ChatError:
            await asyncio.sleep(0.05)
    raise AssertionError(f"{user} could not join")


async def wait_until(condition, timeout=20.0):
    """Poll until condition() is true, or fail after timeout seconds."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not condition():
        if loop.time() > deadline:
            raise AssertionError("timed out waiting for condition")
        await asyncio.sleep(0.01)


def received(out, line):
    """True once `line` was printed (ignoring a trailing stats suffix)."""
    return any(o.startswith(line) for o in out)


async def connect_pair(url, state_dir, model, key_alice="sesame", key_bob="sesame"):
    """Alice and Bob each /add the other; return both controllers and outputs."""
    alice, alice_out = await make_user("alice", url, state_dir)
    bob, bob_out = await make_user("bob", url, state_dir)
    await alice.handle_line(f"/add bob {model} {key_alice}")
    await bob.handle_line(f"/add alice {model} {key_bob}")
    return alice, alice_out, bob, bob_out


@pytest.mark.parametrize("model", ["uniform", "shakespeare_char"])
def test_chat_both_ways(model, tmp_path, request):
    if model == "shakespeare_char":
        request.getfixturevalue("shakespeare")  # skips when the model bank isn't available

    async def scenario():
        server, url = await start_relay_url()
        alice, alice_out, bob, bob_out = await connect_pair(url, tmp_path, model)
        await wait_until(lambda: alice.status["bob"] == VERIFIED and bob.status["alice"] == VERIFIED)

        await alice.handle_line("/stats on")
        await alice.handle_line("Good morrow, gentle cousin!")
        await wait_until(lambda: received(bob_out, "[alice] Good morrow, gentle cousin!"))
        await bob.handle_line("And to thee, sweet Alice.\nFarewell.")  # handle_line strips, newline inside stays
        await wait_until(lambda: received(alice_out, "[bob] And to thee, sweet Alice."))
        assert any(o.startswith("  -> bob (27 chars ->") for o in alice_out)

        await alice.handle_line("/peers")
        assert any("bob" in o and VERIFIED in o for o in alice_out)
        await alice.close(), await bob.close()
        server.close()
    asyncio.run(scenario())


def test_different_keys_mismatch(tmp_path):
    async def scenario():
        server, url = await start_relay_url()
        alice, alice_out, bob, bob_out = await connect_pair(url, tmp_path, "uniform", "key-one", "key-two")
        await wait_until(lambda: alice.status["bob"] == MISMATCH and bob.status["alice"] == MISMATCH)
        await alice.handle_line("can you read this?")
        await wait_until(lambda: any("can't be decoded" in o for o in bob_out))
        await alice.close(), await bob.close()
        server.close()
    asyncio.run(scenario())


def test_message_before_add_is_held(tmp_path):
    async def scenario():
        server, url = await start_relay_url()
        alice, _ = await make_user("alice", url, tmp_path)
        bob, bob_out = await make_user("bob", url, tmp_path)
        await alice.handle_line("/add bob uniform sesame")
        await alice.handle_line("hello there, bob")
        await wait_until(lambda: any("wants to chat" in o for o in bob_out) and any("held" in o for o in bob_out))
        await bob.handle_line("/add alice uniform sesame")
        await wait_until(lambda: received(bob_out, "[alice] hello there, bob"))
        await wait_until(lambda: alice.status["bob"] == VERIFIED and bob.status["alice"] == VERIFIED)
        await alice.close(), await bob.close()
        server.close()
    asyncio.run(scenario())


def test_peers_survive_restart_and_offline_delivery(tmp_path):
    async def scenario():
        server, url = await start_relay_url()
        alice, alice_out, bob, bob_out = await connect_pair(url, tmp_path, "uniform")
        await wait_until(lambda: alice.status["bob"] == VERIFIED)
        await bob.close()
        await alice.handle_line("sent while you were away")  # queued by the relay

        bob2, bob2_out = await make_user("bob", url, tmp_path)  # same state dir -> peers restored
        assert "alice" in bob2.peers
        await wait_until(lambda: received(bob2_out, "[alice] sent while you were away"))
        await wait_until(lambda: bob2.status["alice"] == VERIFIED)
        await alice.close(), await bob2.close()
        server.close()
    asyncio.run(scenario())


def test_command_errors(tmp_path):
    async def scenario():
        server, url = await start_relay_url()
        alice, out = await make_user("alice", url, tmp_path)
        await alice.handle_line("hello")
        await alice.handle_line("/add bob nosuchmodel k")
        await alice.handle_line("/add alice uniform k")
        await alice.handle_line("/to nobody")
        await alice.handle_line("/frobnicate")
        await alice.handle_line("/add bob uniform k")
        await alice.handle_line("café \"quoted\"")
        joined = "\n".join(out)
        for expected in ["no current peer", "unknown model", "can't add yourself", "usage: /to",
                         "unknown command", "not in the model's vocabulary"]:
            assert expected in joined, expected
        await alice.handle_line("/remove bob")
        assert alice.peers == {} and alice.current is None
        assert await alice.handle_line("/quit") is False
        await alice.close()
        server.close()
    asyncio.run(scenario())


def test_cli_smoke(tmp_path):
    """The prompt_toolkit front end starts, runs commands from (piped) input, and quits cleanly."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    async def scenario():
        server, url = await start_relay_url()
        with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
            pipe.send_text("/models\r/help\r/quit\r")
            assert await asyncio.wait_for(run_cli("alice", url, tmp_path), 20) == 0
        server.close()
    asyncio.run(scenario())
