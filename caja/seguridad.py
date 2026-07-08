"""Manejo de contraseñas: nunca se almacenan en texto plano.

Se usa PBKDF2-HMAC-SHA256 con sal aleatoria por usuario (plan.md §6.9).
"""

import hashlib
import hmac
import os

_ITERACIONES = 100_000


def nueva_sal() -> str:
    return os.urandom(16).hex()


def hash_clave(clave: str, sal: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", clave.encode("utf-8"), bytes.fromhex(sal), _ITERACIONES
    ).hex()


def verificar_clave(clave: str, sal: str, hash_guardado: str) -> bool:
    return hmac.compare_digest(hash_clave(clave, sal), hash_guardado)
