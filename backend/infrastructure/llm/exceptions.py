class OllamaClientError(RuntimeError):
    """Ollama 요청 또는 응답 처리 실패."""


class OllamaModelNotFoundError(OllamaClientError):
    """요청한 모델이 설치되어 있지 않음."""


class OllamaIncompleteResponseError(OllamaClientError):
    """Ollama가 완료되지 않은 응답을 반환함."""


class OllamaResponseParseError(OllamaClientError):
    """Ollama 응답 파싱 실패."""


class OllamaLowQualityResponseError(OllamaClientError):
    """응답이 너무 짧거나 반복이 심함."""
