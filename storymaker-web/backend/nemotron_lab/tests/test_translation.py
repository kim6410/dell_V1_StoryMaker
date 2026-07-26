from backend.schemas import LabRequest
from backend.service import NemotronLabService


def test_translation_does_not_call_model_in_shell_phase():
    request = LabRequest(mode="translate", text="안녕하세요", source_language="ko", target_language="en")
    response = NemotronLabService().execute(request)
    assert response.ok is False
    assert response.status == "shell_only"
