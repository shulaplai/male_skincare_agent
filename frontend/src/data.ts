import type { Conversation, MemoryItem, Message, SkinScore, TimelineEvent } from './types'

const PHOTO = `data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='560' height='300'><defs><linearGradient id='s' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%23e9b8a0'/><stop offset='1' stop-color='%23c98a6a'/></linearGradient></defs><rect width='560' height='300' fill='url(%23s)'/><circle cx='280' cy='150' r='95' fill='%23d9a582'/><circle cx='235' cy='130' r='30' fill='%23e0b090'/><circle cx='330' cy='170' r='20' fill='%23c96a55'/></svg>`

export const initialConversations: Conversation[] = [
  { id: 'face', bodyPart: '面部皮膚', icon: '🧔', days: 47, isDefault: true },
]

export const initialMessages: Record<string, Message[]> = {
  face: [
    {
      id: 'm1',
      role: 'user',
      text: '噚晚打邊爐食咗辣底，今朝下巴就爆咗兩粒，仲有少少泛紅。',
      time: '09:12',
      photo: PHOTO,
    },
    {
      id: 'm2',
      role: 'coach',
      text: '收到，辛苦晒 💛 我對比咗你 5 日前嗰張 baseline，下巴多咗兩粒新暗瘡（下顎線位置），泛紅 +6%。而呢排唯一變數係上星期開始用嗰支新 toner。我哋一步步嚟：',
      time: '09:12',
      analysis: {
        title: '今日皮膚分析',
        metrics: [
          { key: '油光', value: '-18%', dir: 'good', note: '改善' },
          { key: '泛紅', value: '+6%', dir: 'bad', note: '輕微' },
          { key: '新暗瘡', value: '+2', dir: 'bad', note: '下顎線' },
        ],
        advice: [
          '暫停新 toner 3 日 —— 等皮膚返到 baseline，再單獨重試確認。',
          '今晚補水 —— 辣食令表皮失水，B5 精華修復屏障。',
          '未來 7 日避辣 + 高糖 —— 你每次爆瘡前，飲食紀錄都有呢兩樣。',
        ],
      },
    },
    {
      id: 'm3',
      role: 'user',
      text: '咁即係支 toner 唔啱我？定係辣嘢先係主因？',
      time: '09:15',
    },
    {
      id: 'm4',
      role: 'coach',
      text: '而家證據未夠，我當「疑似」處理（confidence 0.61）。做法好簡單：停 toner、避辣一星期睇下巴有冇清返；清咗再單獨加返 toner 兩日。呢個係「單一變數」測試，唔好一次改幾樣呀～',
      time: '09:15',
    },
  ],
}

export const memoryItems: MemoryItem[] = [
  { kind: 'derived', text: 'T 字位偏油，兩頰中性', confidence: 0.82 },
  { kind: 'derived', text: '新 toner（疑似致痘）', confidence: 0.61 },
  { kind: 'pref', text: '鍾意清爽、唔油膩質地' },
  { kind: 'fact', text: 'Baseline 相 · 2025-12-01 存檔' },
]

export const timeline: TimelineEvent[] = [
  { date: '12-12', text: '開始用新 toner（水楊酸）' },
  { date: '12-13', text: '打邊爐 · 辣底' },
  { date: '12-14', text: '下巴爆瘡 +2 · 泛紅' },
]

export const score: SkinScore = {
  value: 78,
  delta: '▲ +6 月比',
  series: [0.8, 0.7, 0.75, 0.57, 0.5, 0.33, 0.25],
  metrics: [
    { key: '油光', value: '-18%', dir: 'good' },
    { key: '泛紅', value: '+6%', dir: 'bad' },
    { key: '暗瘡', value: '+2', dir: 'bad' },
  ],
}

export const helloText =
  '早晨呀阿軒 ☀️ 今日塊面感覺點？可以影張相，或者直接話我知食咗咩、用咗咩，我會一路記住幫你追蹤。'
