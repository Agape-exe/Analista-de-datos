import pytest

from app.evaluation.metrics import TimingRecorder


def test_timing_including_failure() -> None:
    recorder = TimingRecorder()
    with recorder.measure("stage"):
        pass
    with pytest.raises(RuntimeError), recorder.measure("failed"):
        raise RuntimeError("test")
    assert recorder.durations["stage"] >= 0
    assert recorder.durations["failed"] >= 0
