"""Short random identifiers: nanoid over letters and digits only (no ``-`` or ``_``), never uuid4."""

from nanoid import generate

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def new_id(size: int = 21) -> str:
    return generate(ALPHABET, size)
