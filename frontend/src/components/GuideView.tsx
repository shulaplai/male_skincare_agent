import { useEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { Guide, GuideBlock, GuideSection } from '../types'

/**
 * 「男士護膚基本資料」，左目錄 + 右正文。
 *
 * 內容由 `GET /api/guide` 嚟（backend `app/guide.py`），其中「應該用咩產品」一節係由
 * `recommend.RULES` **生成** —— 所以指南同 agent 推薦唔可能唔一致。
 *
 * 兩件事刻意：
 * 1. **引用資料逐節列出**。每句有根據嘅嘢都可以追返 corpus 出處；冇引文嘅（例如
 *    「一次只加一樣新產品」）喺內文已經標明「app 建議，唔係文獻結論」——
 *    UI 唔可以幫佢哋扮成有根據。
 * 2. **圖片係 CSS 佔位方塊**，唔係真圖。`image_id` 有值就畫一個標明「示意圖（佔位）」嘅框，
 *    唔會令你以為有真圖。
 */

/** `**粗體**` 嘅極簡渲染。內容係我哋自己寫嘅（唔係用戶輸入），所以唔使 sanitize。 */
function RichText({ text }: { text: string }) {
  const parts = text.split('**')
  return (
    <>
      {parts.map((p, i) => (i % 2 === 1 ? <strong key={i}>{p}</strong> : <span key={i}>{p}</span>))}
    </>
  )
}

function ImagePlaceholder({ caption }: { caption: string }) {
  return (
    <figure className="guide-figure">
      <div className="guide-image-slot" role="img" aria-label={`${caption}（圖片佔位）`}>
        <span className="gx" />
        <span className="gy" />
      </div>
      <figcaption>
        {caption}
        <em>未加圖片</em>
      </figcaption>
    </figure>
  )
}

function Citations({ items }: { items: string[] }) {
  if (items.length === 0) return null
  return (
    <div className="guide-cites">
      <span className="k">引用</span>
      {items.map((c) => {
        const [source, title] = c.split(' :: ')
        return (
          <span className="cite" key={c} title={c}>
            {source}
            {title ? ` · ${title.length > 44 ? `${title.slice(0, 44)}…` : title}` : ''}
          </span>
        )
      })}
    </div>
  )
}

function Block({ b }: { b: GuideBlock }) {
  if (b.type === 'para') {
    return (
      <div className="guide-block">
        <p>
          <RichText text={b.text} />
        </p>
        <Citations items={b.citations} />
      </div>
    )
  }
  if (b.type === 'callout') {
    return (
      <div className="guide-block">
        <div className={`guide-callout ${b.tone}`}>
          <RichText text={b.text} />
        </div>
        <Citations items={b.citations} />
      </div>
    )
  }
  if (b.type === 'steps') {
    return (
      <div className="guide-block">
        <ol className="guide-steps">
          {b.items.map((it, i) => (
            <li key={i}>
              <span className="n">{i + 1}</span>
              <span>
                <RichText text={it} />
              </span>
            </li>
          ))}
        </ol>
        <Citations items={b.citations} />
      </div>
    )
  }
  if (b.type === 'list') {
    return (
      <div className="guide-block">
        <ul className="guide-list">
          {b.items.map((it, i) => (
            <li key={i}>
              <RichText text={it} />
            </li>
          ))}
        </ul>
        <Citations items={b.citations} />
      </div>
    )
  }
  if (b.type === 'actives') {
    // 由 backend RULES 生成：每行「<狀況> → 主選：…；次選：…」
    return (
      <div className="guide-block">
        <ul className="guide-actives">
          {b.items.map((it, i) => {
            const [cond, rest] = it.split(' → ')
            const [primary, alternative] = (rest ?? '').split('；次選：')
            return (
              <li key={i}>
                <span className="cond">{cond}</span>
                <span className="row">
                  <span className="tier primary">主選</span>
                  {primary?.replace('主選：', '') ?? it}
                </span>
                {alternative && (
                  <span className="row">
                    <span className="tier alt">次選</span>
                    {alternative}
                  </span>
                )}
              </li>
            )
          })}
        </ul>
        <Citations items={b.citations} />
      </div>
    )
  }
  if (b.type === 'image') {
    return <ImagePlaceholder caption={b.text || '示意圖'} />
  }
  if (b.type === 'sources') {
    return (
      <div className="guide-block">
        <Citations items={b.items.length ? b.items : b.citations} />
      </div>
    )
  }
  return null
}

function SectionBody({ section }: { section: GuideSection }) {
  return (
    <>
      <header className="guide-sec-head">
        <span className="ic" aria-hidden>
          {section.icon}
        </span>
        <h3>{section.title}</h3>
      </header>
      {section.summary && <p className="guide-sec-summary">{section.summary}</p>}
      {section.blocks.map((b, i) => (
        <Block b={b} key={i} />
      ))}
    </>
  )
}

export function GuideView({ onBack }: { onBack?: () => void }) {
  const [guide, setGuide] = useState<Guide | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [active, setActive] = useState<string>('')
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let alive = true
    api
      .getGuide()
      .then((g) => {
        if (!alive) return
        setGuide(g)
        setActive(g.sections[0]?.id ?? '')
      })
      .catch((e: Error) => alive && setError(e.message || '載入失敗'))
    return () => {
      alive = false
    }
  }, [])

  const goTo = (id: string) => {
    setActive(id)
    const el = bodyRef.current?.querySelector(`#guide-${id}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <main className="view full guide">
      <div className="guide-head">
        <div>
          <h2>{guide?.title ?? '男士護膚基本資料'}</h2>
          {guide && <p className="hint">{guide.subtitle}</p>}
        </div>
        {onBack && (
          <button className="btn ghost" onClick={onBack}>
            ← 返設定
          </button>
        )}
      </div>

      {error ? (
        <p className="empty">⚠️ {error}（請確認 backend 已起）</p>
      ) : !guide ? (
        <p className="empty">載入中…</p>
      ) : (
        <div className="guide-body">
          <nav className="guide-toc" aria-label="目錄">
            <div className="k">目錄</div>
            {guide.sections.map((s) => (
              <button key={s.id} className={active === s.id ? 'active' : ''} onClick={() => goTo(s.id)}>
                <span className="ti" aria-hidden>
                  {s.icon}
                </span>
                {s.title}
              </button>
            ))}
            <div className="guide-toc-foot">
              <span className="k">引用資料</span>
              <span className="n">{guide.sources.length} 個 corpus 出處</span>
            </div>
          </nav>

          <div className="guide-content" ref={bodyRef}>
            {guide.sections.map((s) => (
              <section key={s.id} id={`guide-${s.id}`} className="guide-sec">
                <SectionBody section={s} />
              </section>
            ))}

            <section className="guide-sec guide-refs">
              <header className="guide-sec-head">
                <span className="ic" aria-hidden>
                  📚
                </span>
                <h3>引用資料</h3>
              </header>
              <p className="hint">
                下面每一條都係 app 知識庫（`chunks` table）入面真實存在嘅出處 ——
                backend 有 test 逐條核對，寫錯會 FAIL。
              </p>
              <ul className="guide-sourcelist">
                {guide.sources.map((c) => {
                  const [source, title] = c.split(' :: ')
                  return (
                    <li key={c}>
                      <span className="src">{source}</span>
                      <span className="ttl">{title}</span>
                    </li>
                  )
                })}
              </ul>
            </section>

            <p className="hint">
              呢版係參考資料，唔構成醫療意見。有醫療問題請諮詢皮膚科醫生。
            </p>
          </div>
        </div>
      )}
    </main>
  )
}
