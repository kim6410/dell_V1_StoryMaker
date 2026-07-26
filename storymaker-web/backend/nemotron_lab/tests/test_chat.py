from backend.schemas import LabRequest
from backend.service import NemotronLabService


def test_chat_does_not_call_model_in_shell_phase():
    response = NemotronLabService().execute(LabRequest(mode="chat", text="테스트"))
    assert response.ok is False
    assert response.status == "shell_only"
