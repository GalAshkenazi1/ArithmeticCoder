
# Implementation Plan: Peer-to-Peer LLM Arithmetic Chat (`UserClient` & Binary Wire Protocol)

## 1. Architectural Overview & Strategic Context

We are extending an existing character-level Arithmetic Coding engine (`EncDec` + `ModelWrapper`) into a two-party messaging application.

* **Core Paradigm:** Each pair of connected peers shares a dedicated, immutable `PermutedModel` (and thus a dedicated `EncDec` instance, and a shared permutation (save the 'key' -> generate from there)) established upon their initial connection. A single user managing $N$ friends maintains $N$ independent peer-to-peer codec sessions.
* **Compact Binary Transport:** Messages must be serialized into compact raw `bytes` to preserve the actual bit-level compression achieved by the coder.
* **Dumb Relay Server:** Any future network transport (e.g., WebSocket relay) acts strictly as a zero-knowledge byte router; all encoding, decoding, and model inference happen client-side.

---

## 2. Binary Wire Protocol Specification (`MessagePack` Serialization)

To achieve true bandwidth efficiency, `MessagePack` must serialize its dyadic rational $r = \frac{m}{2^k}$ (where $0 \le m < 2^k$) into a compact, deterministic byte frame using Python's `struct` module (Network / Big-Endian byte order `!`).

### Wire Frame Layout

| Field | Size | Type | Description |
| --- | --- | --- | --- |
| `model_fingerprint` | `4 bytes` | `4s` (raw bytes) | First 4 bytes of SHA-256 hash of `(vocab, model_weights_digest, precision_bits)` to verify peer model alignment. |
| `msg_length` | `2 bytes` | `H` (`uint16`) | Original character count ($0 \le L \le 65535$). |
| `bit_length` ($k$) | `2 bytes` | `H` (`uint16`) | Exact bit precision $k$ of the dyadic fraction $r = m / 2^k$ ($0 \le k \le 65535$). |
| `numerator_payload` ($m$) | `ceil(k / 8) bytes` | Big-endian `bytes` | Integer $m$ encoded via `m.to_bytes((k + 7) // 8, "big")`. (0 bytes if $k = 0$). |

### Serialization Rules

1. **Extract $(m, k)$ from `Fraction`:** Given `r = Fraction(num, den)`, since `den` is guaranteed to be a power of 2 ($2^k$), compute `k = den.bit_length() - 1` and `m = num`.
2. **Reconstruct `Fraction` from $(m, k)$:** Compute `r = Fraction(m, 1 << k)`.
3. **Header Overhead:** Fixed **8 bytes** per message + $\lceil k / 8 \rceil$ bytes of compressed payload.

---

## 3. Component Design & Responsibilities

### A. Model Fingerprinting (Addition to `ModelWrapper` or `EncDec`)

* Implement `get_fingerprint() -> bytes`:
* Computes a deterministic 4-byte digest (`hashlib.sha256(...).digest()[:4]`) over the ordered `vocab` characters, `precision_bits`, and a deterministic hash of the model's `state_dict` parameters (or uniform baseline identifier).
* Guarantees that if two peers initialized their connection with mismatched models or vocabularies, `receive_message` fails fast before attempting decoding.



### B. `PeerSession` (Encapsulates a 1-on-1 Link)

Represents the dedicated channel between the local user and a specific peer:

* **Attributes:**
* `peer_id: str`
* `coder: EncDec` (wraps the pair-specific `ModelWrapper`)
* `fingerprint: bytes` (4-byte model digest)


* **Methods:**
* `pack_message(msg: str) -> bytes`: Encodes `msg` via `self.coder.encode(msg)` and serializes the resulting `MessagePack` into the binary wire frame.
* `unpack_message(payload: bytes) -> DecodedResult`: Validates payload length ($\ge 8$ bytes), checks `fingerprint == self.fingerprint` (raising `ModelMismatchError` on mismatch), reconstructs `MessagePack(r, msg_length)`, decodes text via `self.coder.decode(...)`, and returns a structured result containing `text`, `original_bytes`, `compressed_bytes`, and `bits_per_char` ($k / \text{len}(\text{text})$).



### C. `UserClient` (Top-Level User Entity)

Manages the user's identity and dictionary of active peer sessions:

* **Attributes:**
* `user_id: str`
* `sessions: dict[str, PeerSession]` (maps `peer_id -> PeerSession`)


* **Methods:**
* `register_peer(peer_id: str, model_wrapper: ModelWrapper, precision_bits: int = 16) -> bytes`: Instantiates `EncDec(model_wrapper, precision_bits)`, stores the `PeerSession` under `self.sessions[peer_id]`, and returns the 4-byte `fingerprint` for handshake verification.
* `verify_peer_handshake(peer_id: str, peer_fingerprint: bytes) -> bool`: Confirms the remote peer initialized the exact same model.
* `send_to(peer_id: str, text: str) -> bytes`: Delegates to `self.sessions[peer_id].pack_message(text)`.
* `receive_from(peer_id: str, payload: bytes) -> DecodedResult`: Delegates to `self.sessions[peer_id].unpack_message(payload)`.



---

## 4. Implementation Milestones & Delegation Boundaries

### Step 1: Binary Wire Serialization & Fingerprinting

* **Task:** Update `MessagePack` with `.to_bytes(fingerprint: bytes) -> bytes` and `@classmethod .from_bytes(data: bytes) -> tuple[bytes, MessagePack]`. Add `fingerprint()` computation to `ModelWrapper` / `EncDec`.
* **Constraint:** Keep `EncDec.encode` and `EncDec.decode` completely independent of byte-packing logic.

### Step 2: `PeerSession` & `UserClient` Implementation

* **Task:** Create `client.py` implementing `UserClient`, `PeerSession`, `DecodedResult`, and custom exceptions (`PeerNotFoundError`, `ModelMismatchError`, `CorruptedPayloadError`).
* **Constraint:** Enforce strict type hints (`Python 3.11+`), clean separation of concerns, and no global state.

### Step 3: In-Memory Loopback Verification & Compression Benchmark

* **Task:** Create a test suite (`test_p2p_chat.py`) simulating two users (`Alice` and `Bob`) with multiple independent peer connections (e.g., Alice connected to Bob with a Shakespeare model, and Alice connected to Charlie with a Uniform/Code model).
* **Test Cases to Cover:**
1. **Exact Round-Trip:** `Bob` decodes `Alice`'s binary payload back to the exact original string (including edge cases: empty string `""`, single character, multi-paragraph text, punctuation/newlines).
2. **Multi-Peer Isolation:** Messages encoded for `Bob` fail with `ModelMismatchError` if routed to `Charlie`.
3. **Wire Size Verification:** Assert that `len(payload) == 8 + ceil(k / 8)` and verify BPC (Bits Per Character) drops significantly when Shakespearean text is sent over the Shakespeare model compared to a Uniform baseline.



---

## 5. Success Criteria

1. All existing arithmetic coding tests continue to pass without regression.
2. `UserClient` supports multiple concurrent peers, each bound to its own immutable `ModelWrapper`.
3. Serialized wire frames are pure compact `bytes` with deterministic round-trip fidelity ($100\%$ lossless reconstruction).
4. Mismatched models between peers are caught immediately via the 4-byte header fingerprint.