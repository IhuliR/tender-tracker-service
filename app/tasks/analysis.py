from app.ai import OpenAILLMClient
from app.celery_app import celery_app
from app.config import settings
from app.schemas import StatusChangeAnalysisInput

ANALYSIS_TASK_NAME = "tender_tracker.analyze_status_change"


@celery_app.task(name=ANALYSIS_TASK_NAME)
def analyze_status_change(payload: dict[str, object]) -> dict[str, object]:
    data = StatusChangeAnalysisInput.model_validate(payload)

    api_key = settings.openai_api_key
    if api_key is None or not api_key.get_secret_value():
        raise RuntimeError("OPENAI_API_KEY is required for AI analysis")

    client = OpenAILLMClient(
        api_key=api_key.get_secret_value(),
        model=settings.openai_model,
    )
    result = client.analyze_status_change(data)
    return result.model_dump(mode="json")
