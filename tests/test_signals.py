import os
import signal
import time
import threading


def test_sigint_sets_interrupted_flag():
    from delegate.cli import install_signal_handlers, is_interrupted
    import delegate.cli as _cli
    _cli._INTERRUPTED = False  # reset
    install_signal_handlers()

    def _send():
        time.sleep(0.1)
        os.kill(os.getpid(), signal.SIGINT)
    t = threading.Thread(target=_send)
    t.start()
    try:
        time.sleep(0.3)
    except KeyboardInterrupt:
        pass
    t.join()
    assert is_interrupted()
