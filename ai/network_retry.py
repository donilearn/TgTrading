import errno
import socket


_WIN_NETWORK_ERRORS = {10053, 10054, 10060}


def is_retryable_network_error(exc: Exception) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError, socket.timeout)):
        return True

    if isinstance(exc, OSError):
        winerror = getattr(exc, "winerror", None)
        if winerror in _WIN_NETWORK_ERRORS:
            return True
        if exc.errno in {errno.ETIMEDOUT, errno.ECONNRESET, errno.ECONNABORTED, errno.ECONNREFUSED}:
            return True

    name = type(exc).__name__
    return name in {"TransportError", "ReadTimeout", "ConnectTimeout", "RemoteProtocolError"}
