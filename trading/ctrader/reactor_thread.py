import threading

from twisted.internet import reactor

_started = False
_lock = threading.Lock()


def ensure_reactor_running() -> None:
    """Twisted reactor ni alohida daemon thread da ishga tushiradi."""
    global _started
    with _lock:
        if _started:
            return

        def _run() -> None:
            if not reactor.running:
                reactor.run(installSignalHandlers=False)

        thread = threading.Thread(
            target=_run,
            name="ctrader-twisted-reactor",
            daemon=True,
        )
        thread.start()
        _started = True


def call_from_reactor(callback, *args, **kwargs) -> None:
    ensure_reactor_running()
    reactor.callFromThread(callback, *args, **kwargs)
