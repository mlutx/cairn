"""
This file maps model providers to the classes that support them, and to the models that are supported by them (may be out of date).
"""



from agents.llm_consts import (
    ChatAnthropic,
    AnthropicResponse,
    ChatOpenAI,
    OpenAIResponse,
    ChatGemini,
)
from difflib import SequenceMatcher


SUPPORTED_MODELS = {

    "anthropic": {
        "chat_class": ChatAnthropic,
        "response_class": AnthropicResponse,
        "models": [
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-latest",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
        ]
    },

    "openai": {
        "chat_class": ChatOpenAI,
        "response_class": OpenAIResponse,
        "models": [
            "gpt-4.1",
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4",
            "gpt-3.5-turbo",
        ]
    },

    "gemini": {
        "chat_class": ChatGemini,
        "response_class": OpenAIResponse,
        "models": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
            "gemini-2.5-pro",
            "gemini-2.5-pro-preview-05-20",
            "gemini-2.5-flash",
            "gemini-2.5-flash-preview-05-20",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]
    }
}

def find_supported_model_given_model_name(model_name: str, allow_fuzzy_match: bool = False, fuzzy_threshold: float = 0.85) -> tuple[str | None, dict | None]:
    """
    Find the supported model given a model name.

    This function first attempts an exact match against known model names. If no exact match is found
    and allow_fuzzy_match is True, it will attempt to find the closest matching model name using
    string similarity matching. This fuzzy matching helps support new model versions without requiring
    explicit updates to the hardcoded model dictionary.

    Args:
        model_name (str): The name of the model to search for
        allow_fuzzy_match (bool, optional): Whether to allow fuzzy matching if no exact match is found. Defaults to False.
        fuzzy_threshold (float, optional): The minimum similarity score (0-1) required for a fuzzy match. Defaults to 0.85.

    Returns:
        tuple[str | None, dict | None]: A tuple containing:
            - The provider name (or None if no match found)
            - The provider's model info dictionary (or None if no match found)
    """
    # First try exact match
    for provider, model_info in SUPPORTED_MODELS.items():
        if model_name in model_info["models"]:
            return provider, model_info

    # If no exact match and fuzzy matching is allowed, try fuzzy matching
    if allow_fuzzy_match:
        best_match_score = 0
        best_match_provider = None
        best_match_info = None

        for provider, model_info in SUPPORTED_MODELS.items():
            for supported_model in model_info["models"]:
                similarity = SequenceMatcher(None, model_name.lower(), supported_model.lower()).ratio()
                if similarity > best_match_score and similarity >= fuzzy_threshold:
                    best_match_score = similarity
                    best_match_provider = provider
                    best_match_info = model_info

        if best_match_provider:
            return best_match_provider, best_match_info

    return None, None


if __name__ == "__main__":
    print(find_supported_model_given_model_name("gpt-4.1"))
