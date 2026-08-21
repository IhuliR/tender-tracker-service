from typing import Protocol

from app.schemas import StatusChangeAnalysis, StatusChangeAnalysisInput


class LLMClient(Protocol):
    def analyze_status_change(
        self,
        data: StatusChangeAnalysisInput,
    ) -> StatusChangeAnalysis: ...
