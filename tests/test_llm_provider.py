"""Gemini provider wiring tests (409_PROVIDER_ARCHITECTURE.md).

Covers: graceful failure (never raises), and environment-based auto-selection in
the composition root (Backend picks Gemini when GEMINI_API_KEY is set, falls back
to the deterministic template otherwise).
"""

from __future__ import annotations

from detective_monkey.application.container import Backend
from detective_monkey.engines.retrieval.packages import PromptSection, RetrievalPromptPackage
from detective_monkey.infrastructure.platform import EnvConfiguration
from detective_monkey.infrastructure.providers import GeminiProvider, TemplateLLMProvider


def _prompt() -> RetrievalPromptPackage:
    return RetrievalPromptPackage(
        system_prompt="You are a mentor.",
        sections=(PromptSection("Knowledge", "Data Scientist: analyzes data."),),
        user_question="Tell me about data scientist",
        template_version="v1",
    )


def test_gemini_provider_never_raises_on_failure():
    provider = GeminiProvider("definitely-invalid-key", timeout=5.0)
    result = provider.generate(_prompt())
    assert result == ""  # graceful degradation signal; never an exception


def test_gemini_provider_rejects_empty_key():
    try:
        GeminiProvider("")
    except ValueError:
        pass
    else:
        raise AssertionError("GeminiProvider should reject an empty api_key")


def test_env_configuration_overrides_take_precedence():
    cfg = EnvConfiguration(overrides={"GEMINI_API_KEY": "from-override"})
    assert cfg.get("GEMINI_API_KEY") == "from-override"
    assert cfg.get("DOES_NOT_EXIST", "fallback") == "fallback"


def test_backend_selects_gemini_when_env_key_present(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    backend = Backend()
    assert isinstance(backend.explanation_engine._llm, GeminiProvider)
    assert isinstance(backend.agent._deps.llm, GeminiProvider)


def test_backend_falls_back_to_template_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    backend = Backend()
    assert isinstance(backend.explanation_engine._llm, TemplateLLMProvider)


def test_explicit_llm_injection_overrides_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    backend = Backend(llm=TemplateLLMProvider())
    assert isinstance(backend.explanation_engine._llm, TemplateLLMProvider)
