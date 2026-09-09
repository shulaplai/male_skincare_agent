import { LAYOUTS } from './defs'
import { useLayout } from './LayoutContext'

/** 三套結構嘅縮圖（純 CSS wireframe，唔係 screenshot） */
function Thumb({ id }: { id: string }) {
  if (id === 'chat')
    return (
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
    )
  if (id === 'journal')
    return (
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
    )
  return (
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
  )
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
            {l.icon} {l.name}
            <em>{l.tagline}</em>
          </span>
          <span className="desc">{l.blurb}</span>
        </button>
      ))}
    </div>
  )
}
