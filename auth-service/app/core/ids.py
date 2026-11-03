"""UUID v7 (RFC 9562): ordenável pelo instante de criação e não sequencial. Ver docs/adr/010."""

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    ms = int(time.time() * 1000)
    aleatorio = int.from_bytes(os.urandom(10), "big")
    rand_a = aleatorio >> 62 & 0xFFF
    rand_b = aleatorio & ((1 << 62) - 1)
    return uuid.UUID(int=ms << 80 | 0x7 << 76 | rand_a << 64 | 0b10 << 62 | rand_b)
