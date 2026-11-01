from agent.prompt import SYSTEM_PROMPT


def test_system_prompt_refuses_out_of_scope_requests() -> None:
    lowered = SYSTEM_PROMPT.lower()
    assert "non-negotiable" in lowered
    assert "i can only help with this mep design." in lowered
    for term in ("coding", "math", "trivia", "palindrome"):
        assert term in lowered


def test_system_prompt_keeps_answers_short() -> None:
    lowered = SYSTEM_PROMPT.lower()
    assert "under 120 words" in lowered
    assert "at most 4 short bullets" in lowered
