/* ============================================================
   AI 層 —— OpenAI-compatible chat completions
   - 支援視覺（image_url）／串流（SSE）／JSON mode
   - 錯誤分類：auth / not-found / image-not-supported / rate-limit / server / network / bad-request
   ============================================================ */

import type { AiSettings } from './types';

export type ContentPart =
  | { type: 'text'; text: string }
  | { type: 'image_url'; image_url: { url: string } };

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string | ContentPart[];
}

export class AiError extends Error {
  code: 'auth' | 'not-found' | 'image-not-supported' | 'rate-limit' | 'server' | 'network' | 'bad-request' | 'timeout' | 'aborted' | 'unknown';
  constructor(code: AiError['code'], message: string) {
    super(message);
    this.name = 'AiError';
    this.code = code;
  }
}

export interface ChatOptions {
  settings: AiSettings;
  model: string;
  messages: ChatMessage[];
  json?: boolean;
  stream?: boolean;
  signal?: AbortSignal;
  timeoutMs?: number;
  onChunk?: (delta: string) => void;
  temperature?: number;
}

export interface ChatResult {
  text: string;
  model: string;
  vision: boolean;
}

/* 已知純文字 model —— 直接跳過視覺（慳一次失敗 call） */
const TEXT_ONLY_MODELS = ['deepseek-chat', 'deepseek-reasoner', 'gpt-3.5-turbo'];

export function modelLooksTextOnly(model: string): boolean {
  const m = model.toLowerCase();
  return TEXT_ONLY_MODELS.some((t) => m.includes(t));
}

export interface ProviderPreset {
  id: string;
  name: string;
  baseUrl: string;
  visionModel: string;
  textModel: string;
  strongModel: string;
  textOnly: boolean;
  /** 香港可直連（唔使 VPN） */
  hk?: boolean;
  /** 揀選後顯示嘅提示（例如 CORS 風險） */
  note?: string;
}

export const PROVIDER_PRESETS: ProviderPreset[] = [
  {
    id: 'openai',
    name: 'OpenAI（支援睇相）',
    baseUrl: 'https://api.openai.com/v1',
    visionModel: 'gpt-4o-mini',
    textModel: 'gpt-4o-mini',
    strongModel: 'gpt-4o',
    textOnly: false,
    note: '⚠️ 香港 IP 官方唔支援（403），要用 VPN 或者經 proxy。',
  },
  {
    id: 'deepseek',
    name: 'DeepSeek（純文字）',
    baseUrl: 'https://api.deepseek.com/v1',
    visionModel: 'deepseek-chat',
    textModel: 'deepseek-chat',
    strongModel: 'deepseek-chat',
    textOnly: true,
    hk: true,
    note: '香港直連；純文字，睇相會自動降級為文字分析。',
  },
  {
    id: 'gemini',
    name: 'Google Gemini（睇相，香港直連）',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai/',
    visionModel: 'gemini-2.0-flash',
    textModel: 'gemini-2.0-flash',
    strongModel: 'gemini-2.5-flash',
    textOnly: false,
    hk: true,
    note: '官方 OpenAI-compatible 端點；用 AI Studio key；有免費額度。CORS 大概率開咗，實測最準。',
  },
  {
    id: 'openrouter',
    name: 'OpenRouter（多 model，香港直連）',
    baseUrl: 'https://openrouter.ai/api/v1',
    visionModel: 'openai/gpt-4o-mini',
    textModel: 'openai/gpt-4o-mini',
    strongModel: 'openai/gpt-4o',
    textOnly: false,
    hk: true,
    note: '一個 key 用晒 GPT-4o／Gemini／Qwen-VL 等視覺 model；設計上支援 client-side。香港延遲要實測。',
  },
  {
    id: 'qwen',
    name: '阿里雲百煉 Qwen-VL（睇相，香港直連）',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    visionModel: 'qwen-vl-plus',
    textModel: 'qwen-vl-plus',
    strongModel: 'qwen-vl-max',
    textOnly: false,
    hk: true,
    note: '官方「兼容 OpenAI 接口」；CORS 未確認，撳「測試連線」就知。',
  },
  {
    id: 'glm',
    name: '智譜 GLM-4V（睇相，香港直連）',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    visionModel: 'glm-4v-plus',
    textModel: 'glm-4v-plus',
    strongModel: 'glm-4v-plus',
    textOnly: false,
    hk: true,
    note: '支援圖像輸入；CORS 未確認，撳「測試連線」就知。',
  },
  {
    id: 'siliconflow',
    name: 'SiliconFlow（開放視覺模型，香港直連）',
    baseUrl: 'https://api.siliconflow.cn/v1',
    visionModel: 'Qwen/Qwen2.5-VL-7B-Instruct',
    textModel: 'Qwen/Qwen2.5-VL-7B-Instruct',
    strongModel: 'Qwen/Qwen2.5-VL-72B-Instruct',
    textOnly: false,
    hk: true,
    note: '開放視覺模型集散地（Qwen-VL 等），有免費額度；CORS 未確認，撳「測試連線」就知。',
  },
  {
    id: 'custom',
    name: '自訂（OpenAI-compatible）',
    baseUrl: '',
    visionModel: 'gpt-4o-mini',
    textModel: 'gpt-4o-mini',
    strongModel: 'gpt-4o',
    textOnly: false,
  },
];

function endpoint(baseUrl: string): string {
  return `${baseUrl.replace(/\/+$/, '')}/chat/completions`;
}

export async function chatCompletion(opts: ChatOptions): Promise<ChatResult> {
  const { settings, model, messages, json, stream, signal, timeoutMs, onChunk, temperature } = opts;
  const ctrl = new AbortController();
  const outer = signal;
  const onOuterAbort = () => ctrl.abort();
  outer?.addEventListener('abort', onOuterAbort);

  let timer: ReturnType<typeof setTimeout> | undefined;
  if (timeoutMs) {
    timer = setTimeout(() => ctrl.abort(), timeoutMs);
  }

  const body: Record<string, unknown> = {
    model,
    messages,
    temperature: temperature ?? 0.55,
    stream: !!stream,
  };
  if (json) body.response_format = { type: 'json_object' };

  try {
    const res = await fetch(endpoint(settings.baseUrl), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${settings.apiKey}`,
      },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => '');
      const lower = errText.toLowerCase();
      if (res.status === 401 || res.status === 403) {
        throw new AiError('auth', 'API key 無效或無權限（401/403）。請去「設定」檢查。');
      }
      if (res.status === 404) {
        throw new AiError('not-found', '模型或 endpoint 唔存在（404）。請檢查 model 名稱同 Base URL。');
      }
      if (res.status === 429) {
        throw new AiError('rate-limit', 'API 限流（429）：請稍候再試。');
      }
      if (res.status >= 500) {
        throw new AiError('server', `API 伺服器錯誤（${res.status}）：請稍候再試。`);
      }
      // 400：可能係圖片唔受支援
      const sentImage = messages.some(
        (m) => Array.isArray(m.content) && m.content.some((c) => c.type === 'image_url'),
      );
      if (sentImage && /image|vision|multimodal|visual|input.*not.*support/i.test(lower)) {
        throw new AiError('image-not-supported', `呢個 model（${model}）唔支援睇相，已改用純文字分析。`);
      }
      if (json && /response_format|json/i.test(lower)) {
        throw new AiError('bad-request', `呢個 endpoint 唔支援 JSON mode（${model}）。`);
      }
      throw new AiError('bad-request', `請求被拒（400）：${errText.slice(0, 240)}`);
    }

    if (stream && onChunk) {
      const text = await readStream(res, onChunk, ctrl.signal);
      return { text, model, vision: messagesSentImage(messages) };
    }

    const data = (await res.json()) as {
      choices?: { message?: { content?: string | null } }[];
      model?: string;
    };
    const text = data.choices?.[0]?.message?.content ?? '';
    return { text, model: data.model ?? model, vision: messagesSentImage(messages) };
  } catch (e) {
    if (e instanceof AiError) throw e;
    if (outer?.aborted) throw new AiError('aborted', '已取消');
    if (ctrl.signal.aborted) {
      if (timeoutMs) throw new AiError('timeout', '請求逾時，請稍候再試。');
      throw new AiError('aborted', '已取消');
    }
    throw new AiError('network', '網絡錯誤：瀏覽器直連 API 需要目標 endpoint 支援 CORS；亦請檢查網絡。');
  } finally {
    outer?.removeEventListener('abort', onOuterAbort);
    if (timer) clearTimeout(timer);
  }
}

function messagesSentImage(messages: ChatMessage[]): boolean {
  return messages.some(
    (m) => Array.isArray(m.content) && m.content.some((c) => c.type === 'image_url'),
  );
}

async function readStream(res: Response, onChunk: (d: string) => void, signal: AbortSignal): Promise<string> {
  if (!res.body) throw new AiError('server', '串流回應冇 body');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let full = '';

  const handleLine = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed.startsWith('data:')) return;
    const payload = trimmed.slice(5).trim();
    if (payload === '[DONE]') return;
    try {
      const parsed = JSON.parse(payload) as {
        choices?: { delta?: { content?: string | null } }[];
      };
      const delta = parsed.choices?.[0]?.delta?.content;
      if (delta) {
        full += delta;
        onChunk(delta);
      }
    } catch {
      /* 忽略無法解析嘅 SSE 行 */
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) handleLine(line);
    if (signal.aborted) throw new AiError('aborted', '已取消');
  }
  if (buffer.trim()) handleLine(buffer);
  return full;
}

/** 設定頁用：極細請求測試連線 */
export async function testConnection(settings: AiSettings): Promise<string> {
  const result = await chatCompletion({
    settings,
    model: settings.textModel,
    messages: [{ role: 'user', content: '請回覆：OK' }],
    timeoutMs: 20_000,
  });
  return result.text;
}

/* 串流取消 helper */
export function makeAborter(): { signal: AbortSignal; abort: () => void } {
  const ctrl = new AbortController();
  return { signal: ctrl.signal, abort: () => ctrl.abort() };
}
