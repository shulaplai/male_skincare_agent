# `skincoach-4p.pdf` — 4 頁專案摘要（2026-10-23）

交付物：`docs/skincoach-4p.pdf`（A4、4 頁、約 3.2 MB）。內容：

1. 產品與流程（5-node flow 圖、四欄數字、對話截圖帶）
2. AI 怎樣處理一個 turn（node 表、prompt 決定、可靠性、`SkinAnalysis` JSON）
3. 技術選型與 RAG（stack 表、hybrid 檢索、資料模型、**「點解揀呢套 stack」六張卡**：LangGraph／SQLite／Pydantic／fastembed＋hybrid／React＋TS／DeepSeek。呢頁唔放截圖 —— 用戶要求用嚟講技術理由）
4. 證據（可重跑的驗證表、指南截圖、「如果只記住一句」）

按用戶 2026-10-23 要求**刻意唔放**：已知邊界、三個真撞過嘅難題、下一步。

## 點樣再生成

1. 起 backend（`:8001`）同 frontend（`:5173`），截圖（2× DPR）：

   ```bash
   cd frontend && node -e "…"   # 見下面 capture 節錄，或直接用 Playwright codegen
   ```

   需要：`shot-chat.png`（1280×860，`?layout=chat&scene=chat`）、`shot-progress-chat.png`（`?layout=chat&scene=progress`）、`shot-guide.png`（`?layout=chat&scene=guide`）、`shot-mobile-home.png`（390×844）。**全部用同一個 layout（`chat`）拍**，否則側欄位置同顏色會唔一致。

2. 用 Pillow 裁一條「回覆＋分析卡」band（全闊、y 300–1400 @2×）：

   ```bash
   backend/.venv/bin/python -c "from PIL import Image; im=Image.open('/tmp/shot-chat.png'); im.crop((0,300,im.width,1400)).save('/tmp/crop-chat.png')"
   ```

3. 用 Chromium 把 `skincoach-4p.source.html` 印成 PDF（`preferCSSPageSize`、四邊 margin 0、`printBackground`）：

   ```bash
   cd frontend && node -e "
   import('playwright').then(async ({chromium}) => {
     const b = await chromium.launch(); const p = await b.newPage()
     await p.goto('file://$PWD/../docs/deck/skincoach-4p.source.html')
     await p.pdf({ path: '../docs/skincoach-4p.pdf', format: 'A4', printBackground: true,
       margin: {top:0,right:0,bottom:0,left:0}, preferCSSPageSize: true })
     await b.close()
   })"
   ```

## 注意

- `skincoach-4p.source.html` **唔入 git**（3 MB、base64 內嵌圖）。要改內容就改佢再印。
- 截圖係真帳戶 UI；相片本身喺 app 內預設模糊（`BlurPhoto`），所以 PDF 亦係模糊版本。
- 字型用系統 `PingFang HK`／`Songti SC`，所以喺 macOS 上印最準。
