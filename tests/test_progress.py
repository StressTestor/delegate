import io
import time
from delegate.progress import Heartbeat


def test_heartbeat_emits_line_after_interval():
    stream = io.StringIO()
    hb = Heartbeat(interval_s=0.1, stream=stream)
    with hb.running(label="p1/m1 task=t1"):
        time.sleep(0.25)
    out = stream.getvalue()
    assert out.count("p1/m1 task=t1") >= 2

def test_heartbeat_no_output_if_exits_fast():
    stream = io.StringIO()
    hb = Heartbeat(interval_s=1.0, stream=stream)
    with hb.running(label="x"):
        pass
    assert stream.getvalue() == ""
