from backend.service import NemotronLabService


def test_shell_starts_offline():
    status = NemotronLabService().status()
    assert status["enabled"] is False
    assert status["status"] == "offline"
    assert status["queue_isolated"] is True
    assert status["storymaker_worker_access"] is False
