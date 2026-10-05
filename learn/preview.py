#!/usr/bin/env python3
"""把 `learn/` 嘅 markdown 轉成「一撳就開」嘅 HTML（靚啲、連結可撳、支援手機）。

為咩要有呢個：`.md` 檔用 TextEdit／Finder 開係一堆 raw markdown，
表同 code block 全部散開，相對連結又唔可撳。呢個 script 產生一版網頁。

跑法（由 repo root 或 learn/ 都可以）：

    ./backend/.venv/bin/python learn/preview.py
    # 然後
    open learn/_preview/index.html

特性：
  * 零 Python 依賴 —— markdown → HTML 交俾 `npx marked`（首次會下載，之後有 cache）
  * 產生嘅檔案喺 `learn/_preview/`（已 gitignore，唔會 commit）
  * 側欄列出全部章節；`.md` 連結自動改成 `.html`，所以章節之間撳得通
  * 純靜態：唔需要起 server，雙擊／`open` 就睇得（用手機睇就先 `python3 -m http.server`）

⚠️ 呢個 script 唔屬於課程內容，係「睇課程嘅工具」。課程本身仍然係 `.md`，
   改完 markdown 要重跑一次先見到新版本。
"""
from __future__ import annotations

import html
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "_preview"

# 側欄次序：README 先，之後順號，最後兩份附錄
ORDER = [
    "README.md",
    "00-what-is-an-agent.md",
    "01-harness.md",
    "02-llm.md",
    "03-embeddings-rag.md",
    "04-agent-loop.md",
    "05-python-runtime.md",
    "06-writing-eval.md",
    "07-labs.md",
    "08-glossary.md",
    "09-next-steps.md",
    "walkthrough-lab03.md",
    "exercises.md",
]

# 側欄分組（用嚟加小標題）
GROUPS = [
    ("開始", ["README.md", "00-what-is-an-agent.md"]),
    ("核心", ["01-harness.md", "02-llm.md", "03-embeddings-rag.md", "04-agent-loop.md", "05-python-runtime.md"]),
    ("驗證", ["06-writing-eval.md"]),
    ("參考", ["07-labs.md", "08-glossary.md", "09-next-steps.md"]),
    ("附錄", ["walkthrough-lab03.md", "exercises.md"]),
]

# ⚠️ 唔好讀 `npm_config_cache` —— 呢部機嘅 shell 已經 export 咗一個 *root-owned* 嘅
# `~/.npm`（EPERM 嘅源頭）。用自己嘅 cache 路徑，並經 `--cache` 明確傳落 npm。
NPM_CACHE = os.environ.get("SKC_NPM_CACHE") or "/tmp/npmcache-npx"

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-HK">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · SkinCoach 教材</title>
<style>
:root {{
  --bg: #faf8f7; --bg2: #ffffff; --ink: #1d1a19; --ink2: #57504d;
  --line: #e5dedb; --accent: #a4435f; --codebg: #f2edeb; --mark: #fff3d6;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #17151a; --bg2: #201d23; --ink: #ece8e6; --ink2: #a9a2a0;
    --line: #332f36; --accent: #e88fa9; --codebg: #2a262d; --mark: #3d3418;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.75 -apple-system, "SF Pro TC", "PingFang HK", "Helvetica Neue", sans-serif;
}}
.wrap {{ display: flex; align-items: flex-start; }}
nav {{
  position: sticky; top: 0; height: 100vh; overflow-y: auto; flex: 0 0 244px;
  background: var(--bg2); border-right: 1px solid var(--line); padding: 20px 14px 40px;
}}
nav .brand {{ font-weight: 700; font-size: 15px; margin: 0 6px 4px; }}
nav .sub {{ font-size: 12px; color: var(--ink2); margin: 0 6px 18px; }}
nav h3 {{
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--ink2); margin: 18px 6px 6px; font-weight: 600;
}}
nav a {{
  display: block; padding: 5px 8px; border-radius: 6px; font-size: 14px;
  color: var(--ink); text-decoration: none; line-height: 1.45;
}}
nav a:hover {{ background: var(--codebg); }}
nav a.cur {{ background: var(--accent); color: #fff; }}
main {{ flex: 1 1 auto; min-width: 0; padding: 40px 40px 120px; max-width: 900px; }}
h1 {{ font-size: 30px; line-height: 1.3; margin: 0 0 20px; }}
h2 {{ font-size: 22px; margin: 40px 0 12px; padding-top: 12px; border-top: 1px solid var(--line); }}
h3 {{ font-size: 17px; margin: 28px 0 8px; }}
h4 {{ font-size: 15px; margin: 20px 0 6px; color: var(--ink2); }}
a {{ color: var(--accent); }}
p, li {{ color: var(--ink); }}
li {{ margin: 4px 0; }}
code {{
  background: var(--codebg); padding: 2px 5px; border-radius: 4px;
  font: 13.5px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
  word-break: break-word;
}}
pre {{
  background: var(--codebg); padding: 14px 16px; border-radius: 8px;
  overflow-x: auto; border: 1px solid var(--line);
}}
pre code {{ background: none; padding: 0; font-size: 13px; }}
blockquote {{
  margin: 16px 0; padding: 12px 16px; border-left: 3px solid var(--accent);
  background: var(--bg2); border-radius: 0 8px 8px 0; color: var(--ink2);
}}
blockquote p {{ margin: 4px 0; color: var(--ink2); }}
table {{
  border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 14px;
  display: block; overflow-x: auto;
}}
th, td {{ border: 1px solid var(--line); padding: 7px 10px; text-align: left; vertical-align: top; }}
th {{ background: var(--codebg); font-weight: 600; white-space: nowrap; }}
hr {{ border: none; border-top: 1px solid var(--line); margin: 36px 0; }}
mark {{ background: var(--mark); }}
.foot {{ margin-top: 60px; font-size: 12.5px; color: var(--ink2); border-top: 1px solid var(--line); padding-top: 14px; }}
@media (max-width: 820px) {{
  .wrap {{ display: block; }}
  nav {{ position: static; height: auto; flex: none; border-right: none; border-bottom: 1px solid var(--line); }}
  main {{ padding: 24px 18px 80px; }}
  h1 {{ font-size: 24px; }}
}}
</style>
</head>
<body>
<div class="wrap">
<nav>
  <p class="brand">🎓 SkinCoach 教材</p>
  <p class="sub">用真 repo 教 AI agent</p>
  {nav}
</nav>
<main>
{body}
<p class="foot">
  由 <code>learn/preview.py</code> 產生（<code>npx marked</code>）—— 原始檔係 <code>learn/{src}</code>。
  改完 markdown 請重跑一次 <code>./backend/.venv/bin/python learn/preview.py</code>。
</p>
</main>
</div>
</body>
</html>
"""


def have_marked() -> list[str]:
    """npx marked 嘅呼叫前綴。

    ⚠️ `--cache` 一定要用**命令行 flag**：`npm_config_cache` 環境變數會被 shell 本身
    export 嘅 `~/.npm` 蓋過（實測 EPERM）。flag 直接俾 npm，唔靠 env 傳遞。
    """
    return ["npx", "--yes", "--cache", NPM_CACHE, "marked"]


def md_to_html(md_path: Path) -> str:
    env = dict(os.environ, npm_config_cache=NPM_CACHE)  # 雙保險：flag 為主
    r = subprocess.run(
        have_marked() + ["-i", str(md_path)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(md_path.parent),
    )
    if r.returncode != 0:
        print(f"✗ marked 失敗：{md_path.name}\n{r.stderr.strip()[:400]}", file=sys.stderr)
        sys.exit(1)
    return r.stdout


def title_of(md_text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", md_text, re.M)
    return m.group(1).strip() if m else fallback


def rewrite_links(html_text: str) -> str:
    """`.md` → `.html`；`README.html` → `index.html`。"""
    html_text = html_text.replace('href="README.md"', 'href="index.html"')
    return re.sub(r'href="([^"]+?)\.md"', r'href="\1.html"', html_text)


def build_nav(current: str) -> str:
    out = []
    for group, files in GROUPS:
        out.append(f"<h3>{html.escape(group)}</h3>")
        for fn in files:
            label = title_of((HERE / fn).read_text(), fn)
            # 側欄只出短標題（去掉「：」之後嘅解釋）
            short = re.split(r"[：:（(]", label)[0].strip() or fn
            href = "index.html" if fn == "README.md" else fn.replace(".md", ".html")
            cls = ' class="cur"' if fn == current else ""
            out.append(f'<a href="{href}"{cls}>{html.escape(short)}</a>')
    return "\n  ".join(out)


def main() -> None:
    missing = [f for f in ORDER if not (HERE / f).exists()]
    if missing:
        print(f"✗ 搵唔到：{', '.join(missing)}（係唔係唔喺 learn/ 度行？）", file=sys.stderr)
        sys.exit(1)

    OUT.mkdir(exist_ok=True)
    print(f"→ 產生 HTML 到 {OUT.relative_to(HERE.parent)}/")
    for fn in ORDER:
        src = HERE / fn
        md = src.read_text()
        body = rewrite_links(md_to_html(src))
        title = title_of(md, fn)
        page = TEMPLATE.format(title=html.escape(title), nav=build_nav(fn), body=body, src=fn)
        dest = OUT / ("index.html" if fn == "README.md" else fn.replace(".md", ".html"))
        dest.write_text(page)
        print(f"  ✓ {fn:<26} → {dest.name}  ({len(page) // 1024} KB, {title[:28]})")

    print(f"\n睇法：\n  open {OUT.relative_to(HERE.parent)}/index.html")
    print(f"  或者喺 {OUT.relative_to(HERE.parent)} 度跑 python3 -m http.server 8099（用手機睇）")


if __name__ == "__main__":
    main()
