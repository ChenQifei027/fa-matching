import os


def _call_anthropic(prompt: str, api_key: str, model: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def _call_openai_compatible(prompt: str, api_key: str, base_url: str, model: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key or "ollama", base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def call_llm(prompt: str) -> str:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

    if not base_url or model.startswith("claude-"):
        return _call_anthropic(prompt, api_key, model)
    return _call_openai_compatible(prompt, api_key, base_url, model)


def get_langchain_llm():
    """返回适配当前配置的 langchain LLM 实例，供 browser-use 使用。"""
    api_key = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

    if not base_url or model.startswith("claude-"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, anthropic_api_key=api_key)

    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, openai_api_key=api_key or "ollama",
                      openai_api_base=base_url)


def llm_is_configured() -> bool:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    if base_url:
        return True
    return bool(api_key)
