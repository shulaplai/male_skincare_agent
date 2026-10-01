import type { LayoutId } from '../types'
import { LAYOUTS } from './defs'
import { useLayout } from './LayoutContext'
import { Icon } from '../components/Icon'

/**
 * 四套結構嘅縮圖（純 CSS wireframe，唔係 screenshot）。
 * 用 `Record<LayoutId, …>` 而唔係 `if`／`switch` chain —— 加新結構時漏咗呢度會**編譯唔過**
 * （以前用 chain，第 4 個 id 會靜靜 render dash 嗰個縮圖）。
 */
const THUMBS: Record<LayoutId, JSX.Element> = {
  chat: (
    <span className="mini mini-chat" aria-hidden>
      <i className="s" />
      <i className="m">
        <b />
        <b />
        <b />
        <b />
      </i>
      <i className="r">
        <b />
        <b />
      </i>
    </span>
  ),
  journal: (
    <span className="mini mini-journal" aria-hidden>
      <i className="s" />
      <i className="m">
        <b />
        <b />
        <b />
        <b />
      </i>
      <i className="r" />
    </span>
  ),
  dash: (
    <span className="mini mini-dash" aria-hidden>
      <i className="m">
        <b />
        <b />
        <b />
        <b />
        <b />
        <b />
      </i>
    </span>
  ),
  mobile: (
    <span className="mini mini-mobile" aria-hidden>
      <i className="top" />
      <i className="body">
        <b />
        <b />
        <b />
      </i>
      <i className="bar">
        <b />
        <b />
        <b />
        <b />
        <b />
      </i>
    </span>
  ),
}

function Thumb({ id }: { id: LayoutId }) {
  return THUMBS[id]
}

/** Settings「介面結構」揀選器：食 LAYOUTS registry，一撳即換＋persist。 */
export function LayoutPicker() {
  const { layout, setLayout } = useLayout()
  return (
    <div className="layout-picker">
      {LAYOUTS.map((l) => (
        <button key={l.id} className={`layout-opt ${layout === l.id ? 'active' : ''}`} onClick={() => setLayout(l.id)}>
          <Thumb id={l.id} />
          <span className="name">
            <Icon name={l.icon} size={16} /> {l.name}
            <em>{l.tagline}</em>
          </span>
          <span className="desc">{l.blurb}</span>
        </button>
      ))}
    </div>
  )
}
