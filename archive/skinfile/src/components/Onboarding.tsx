/* 首次設定（Onboarding）：個人檔案 + 目標 + 疑惑 */

import { useState } from 'react';
import { mutateDb } from '../lib/store';
import { uid, type Goal } from '../lib/types';
import { PhotoUpload } from './PhotoUpload';
import { Field } from './ui';

const SKIN_TYPES = ['油性', '乾性', '混合偏油', '混合偏乾', '中性', '敏感', '唔太清楚'];
const GOAL_PRESETS = ['去暗瘡', '控油', '保濕', '淡暗瘡印', '均勻膚色', '縮毛孔', '抗衰老', '減少敏感'];

export function Onboarding() {
  const [name, setName] = useState('');
  const [skinType, setSkinType] = useState('');
  const [photo, setPhoto] = useState<string | undefined>();
  const [concerns, setConcerns] = useState('');
  const [goals, setGoals] = useState<Goal[]>([]);
  const [error, setError] = useState<string | null>(null);

  const addGoal = (title: string) => {
    if (goals.some((g) => g.title === title)) return;
    setGoals([...goals, { id: uid(), title, status: 'not-started', createdAt: Date.now() }]);
  };

  const save = () => {
    if (!name.trim()) {
      setError('請輸入稱呼（例如「阿俊」）。');
      return;
    }
    if (goals.length === 0) {
      setError('請至少揀一個目標。');
      return;
    }
    try {
      mutateDb((db) => ({
        ...db,
        profile: {
          id: uid(),
          name: name.trim(),
          skinType: skinType || undefined,
          baselinePhoto: photo,
          concerns: concerns.trim(),
          goals,
          createdAt: Date.now(),
        },
      }));
    } catch {
      setError('儲存失敗：瀏覽器儲存空間可能已滿。');
    }
  };

  return (
    <div className="card rise" style={{ maxWidth: 640 }}>
      <div className="kicker">Case Intake · 檔案建立</div>
      <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 900, fontSize: 24, margin: '0 0 4px' }}>
        建立你嘅皮膚檔案
      </h2>
      <p className="muted" style={{ marginTop: 0, fontSize: 13.5 }}>
        上載一張素顏相做 baseline，設定目標，留低你嘅疑惑 —— AI 之後會跟住追蹤。
      </p>

      <div className="grid-2" style={{ marginTop: 16 }}>
        <Field label="稱呼">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：阿俊" />
        </Field>
        <Field label="膚質（自己判斷）">
          <select className="select" value={skinType} onChange={(e) => setSkinType(e.target.value)}>
            <option value="">唔太清楚</option>
            {SKIN_TYPES.filter((s) => s !== '唔太清楚').map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </Field>
      </div>

      <Field label="Baseline 相片" hint="建議：素顏、自然光、正面，之後對比先有意義。">
        <PhotoUpload value={photo} onChange={setPhoto} label="上載素顏相" />
      </Field>

      <Field label="目標（可揀多個）">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {GOAL_PRESETS.map((g) => {
            const on = goals.some((x) => x.title === g);
            return (
              <button
                key={g}
                type="button"
                className={`btn sm ${on ? 'accent' : 'ghost'}`}
                onClick={() => (on ? setGoals(goals.filter((x) => x.title !== g)) : addGoal(g))}
              >
                {on ? '✓ ' : '+ '}{g}
              </button>
            );
          })}
        </div>
      </Field>

      <Field label="疑惑／想改善嘅問題" hint="例如：成日出油點算？暗瘡印幾耐先淡？">
        <textarea
          className="textarea"
          value={concerns}
          onChange={(e) => setConcerns(e.target.value)}
          placeholder="寫低你想 AI 解答嘅問題，例如「T字位成日反光，想知點控油」"
        />
      </Field>

      {error ? <div className="banner err">{error}</div> : null}

      <button className="btn" onClick={save} style={{ marginTop: 6 }}>
        建立檔案 →
      </button>
    </div>
  );
}
