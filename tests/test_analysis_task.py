import json

import pytest
from pydantic import SecretStr

from app.schemas import (
    StatusChangeAnalysis,
    StatusChangeAnalysisInput,
)
from app.tasks import analysis as task_module

VALID_PAYLOAD = {
    "title": "Bridge inspection",
    "description": "Annual structural inspection services",
    "old_status": "draft",
    "new_status": "active",
    "reason": "Tender published",
}


def test_analysis_task_validates_payload_and_returns_json_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received_inputs: list[StatusChangeAnalysisInput] = []
    expected = StatusChangeAnalysis(
        summary="The transition is documented.",
        observations=["A reason was supplied."],
        recommendations=["Review the outcome later."],
    )

    class FakeLLMClient:
        def __init__(self, api_key: str, model: str) -> None:
            assert api_key == "test-key"
            assert model == "test-model"

        def analyze_status_change(
            self,
            data: StatusChangeAnalysisInput,
        ) -> StatusChangeAnalysis:
            received_inputs.append(data)
            return expected

    monkeypatch.setattr(task_module, "OpenAILLMClient", FakeLLMClient)
    monkeypatch.setattr(
        task_module.settings,
        "openai_api_key",
        SecretStr("test-key"),
    )
    monkeypatch.setattr(task_module.settings, "openai_model", "test-model")

    result = task_module.analyze_status_change.run(VALID_PAYLOAD)

    assert received_inputs == [StatusChangeAnalysisInput(**VALID_PAYLOAD)]
    assert result == expected.model_dump(mode="json")
    assert json.loads(json.dumps(result)) == result


def test_analysis_task_requires_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(task_module.settings, "openai_api_key", None)

    with pytest.raises(
        RuntimeError,
        match="OPENAI_API_KEY is required for AI analysis",
    ):
        task_module.analyze_status_change.run(VALID_PAYLOAD)


def test_analysis_task_propagates_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ProviderFailure(Exception):
        pass

    class FailingLLMClient:
        def __init__(self, api_key: str, model: str) -> None:
            pass

        def analyze_status_change(
            self,
            data: StatusChangeAnalysisInput,
        ) -> StatusChangeAnalysis:
            raise ProviderFailure("provider unavailable")

    monkeypatch.setattr(task_module, "OpenAILLMClient", FailingLLMClient)
    monkeypatch.setattr(
        task_module.settings,
        "openai_api_key",
        SecretStr("test-key"),
    )

    with pytest.raises(ProviderFailure, match="provider unavailable"):
        task_module.analyze_status_change.run(VALID_PAYLOAD)
