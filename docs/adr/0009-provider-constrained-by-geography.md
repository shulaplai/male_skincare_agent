# LLM provider 由地理位置決定，唔係由質素決定

文字同 vision 都用 DeepSeek（`deepseek-v4-flash`／`deepseek-v4-flash-vision-exp`）。呢個唔係技術偏好，係約束：香港直連 OpenAI 同 Anthropic 都係 403（唔喺 supported regions），所以兩間嘅任何型號都揀唔到。

**Considered options**：Anthropic／OpenAI —— 唔可行（403）。經第三方 relay／proxy —— 可行但拒絕，因為要將一個有醫療 guardrail 嘅 app 嘅流量交俾一個唔知條款點寫嘅中間人，而呢個 app 處理嘅係用戶嘅自拍。其他 OpenAI-compatible provider（Gemini／OpenRouter／DashScope Qwen／GLM）**技術上**換 base_url ＋ key 就用到，但未實測過，所以唔當係已支持。

**Consequences**：所有 provider 都經同一個 OpenAI-compatible adapter，所以換 provider 係改 config 而唔係改 code。但呢個 adapter 有一支針對 DeepSeek 嘅 workaround（V4 預設開 thinking，而 thinking 唔俾強制 `tool_choice`，所以要關咗 thinking），搬 provider 之前要確認佢唔會被誤當成通用邏輯。另外：即使喺 supported region，model id 有退役期（`deepseek-chat` 2026-07 已經冇咗），所以 config 唔可以當係永久有效。
