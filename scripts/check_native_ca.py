"""Offline Linux image regression: both Python and bundled libpq must load CAs.

Run inside the native image using stdin. No endpoints, credentials or TLS bypass.
Checking Python's ssl context alone misses psycopg-binary's separate OpenSSL.
"""
import ctypes
from pathlib import Path
import ssl

import psycopg  # Initialize the binary implementation before importing it directly.
import psycopg_binary


def verify():
    library = next((Path(psycopg_binary.__file__).parent.parent /
                    'psycopg_binary.libs').glob('libssl*.so*'))
    lib = ctypes.CDLL(str(library))
    signatures = {
        'TLS_client_method': ([], ctypes.c_void_p),
        'SSL_CTX_new': ([ctypes.c_void_p], ctypes.c_void_p),
        'SSL_CTX_set_default_verify_paths': ([ctypes.c_void_p], ctypes.c_int),
        'SSL_CTX_get_cert_store': ([ctypes.c_void_p], ctypes.c_void_p),
        'X509_STORE_get0_objects': ([ctypes.c_void_p], ctypes.c_void_p),
        'OPENSSL_sk_num': ([ctypes.c_void_p], ctypes.c_int),
        'SSL_CTX_free': ([ctypes.c_void_p], None),
    }
    for name, (args, result) in signatures.items():
        function = getattr(lib, name)
        function.argtypes, function.restype = args, result
    context = lib.SSL_CTX_new(lib.TLS_client_method())
    if not context:
        raise ValueError('Missing TLS context')
    try:
        if lib.SSL_CTX_set_default_verify_paths(context) != 1:
            raise ValueError('CA loading failed')
        store = lib.SSL_CTX_get_cert_store(context)
        count = lib.OPENSSL_sk_num(lib.X509_STORE_get0_objects(store))
        # OpenSSL may return success for nonexistent default locations: count roots.
        if count <= 0 or ssl.create_default_context().cert_store_stats()['x509_ca'] <= 0:
            raise ValueError('Missing trusted CAs')
    finally:
        lib.SSL_CTX_free(context)


if __name__ == '__main__':
    try:
        verify()
    except Exception:
        raise SystemExit('Native CA trust check refused') from None
    print('Python and bundled libpq loaded trusted CAs')
