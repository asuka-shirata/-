// サブスクのデータモデル・保存データの移行・日付計算

export type Subscription = {
  id: string
  name: string
  price: number
  /** 毎月の請求日（1〜31）。月末を超える場合は月末に丸める */
  billingDay: number
  /** 無料トライアル終了日（YYYY-MM-DD）。トライアルなしは null */
  trialEndDate: string | null
  /** 「使った」を記録した日付（YYYY-MM-DD）の配列 */
  usageLog: string[]
  /** 登録日（YYYY-MM-DD）。解約候補の判定に使う */
  createdAt: string
}

export const STORAGE_KEY = 'subscription-manager:items'
export const UPCOMING_DAYS = 14
export const SOON_DAYS = 3
export const UNUSED_DAYS = 30

const DAY_MS = 24 * 60 * 60 * 1000

// ---- 日付ユーティリティ（すべてローカル日付で扱う） ----

export function toDateKey(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function fromDateKey(key: string): Date {
  const [y, m, d] = key.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function todayKey(): string {
  return toDateKey(new Date())
}

export function addDays(key: string, days: number): string {
  const date = fromDateKey(key)
  date.setDate(date.getDate() + days)
  return toDateKey(date)
}

/** from から to までの日数（to が未来なら正） */
export function daysBetween(from: string, to: string): number {
  const a = fromDateKey(from)
  const b = fromDateKey(to)
  return Math.round(
    (Date.UTC(b.getFullYear(), b.getMonth(), b.getDate()) -
      Date.UTC(a.getFullYear(), a.getMonth(), a.getDate())) /
      DAY_MS,
  )
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate()
}

/** 請求日をその月の日付に変換（31日→30日など月末に丸める） */
function billingDateIn(year: number, month: number, billingDay: number): Date {
  return new Date(year, month, Math.min(billingDay, daysInMonth(year, month)))
}

export function formatMonthDay(key: string): string {
  const date = fromDateKey(key)
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

// ---- 請求・トライアル ----

export function isTrialActive(sub: Subscription, today: string): boolean {
  return sub.trialEndDate !== null && daysBetween(today, sub.trialEndDate) >= 0
}

/** 今日以降で最初に来る通常の請求日 */
function nextRegularBillingDate(billingDay: number, today: string): string {
  const now = fromDateKey(today)
  const thisMonth = billingDateIn(now.getFullYear(), now.getMonth(), billingDay)
  if (thisMonth >= now) return toDateKey(thisMonth)
  return toDateKey(billingDateIn(now.getFullYear(), now.getMonth() + 1, billingDay))
}

/** 次回請求日。トライアル中はトライアル終了日を初回請求日とみなす */
export function nextChargeDate(sub: Subscription, today: string): string {
  if (isTrialActive(sub, today) && sub.trialEndDate) return sub.trialEndDate
  return nextRegularBillingDate(sub.billingDay, today)
}

// ---- 利用状況 ----

export function usageThisMonth(sub: Subscription, today: string): number {
  const prefix = today.slice(0, 7)
  return sub.usageLog.filter((day) => day.startsWith(prefix)).length
}

/** 1回あたりコスト（小数点以下切り上げ）。未使用なら null */
export function costPerUse(sub: Subscription, today: string): number | null {
  const count = usageThisMonth(sub, today)
  return count === 0 ? null : Math.ceil(sub.price / count)
}

export function lastUsedDate(sub: Subscription): string | null {
  if (sub.usageLog.length === 0) return null
  return [...sub.usageLog].sort()[sub.usageLog.length - 1]
}

/** 直近30日で未使用、かつ登録から30日以上経過していれば解約候補 */
export function isCancelCandidate(sub: Subscription, today: string): boolean {
  if (daysBetween(sub.createdAt, today) < UNUSED_DAYS) return false
  return !sub.usageLog.some((day) => {
    const ago = daysBetween(day, today)
    return ago >= 0 && ago < UNUSED_DAYS
  })
}

// ---- デモデータ（実行日を基準に相対的に作る） ----

function dayOfMonthAfter(today: string, days: number): number {
  return fromDateKey(addDays(today, days)).getDate()
}

/** 今月の1日から今日までのうち、間引いた日付を利用履歴にする */
function frequentUsageThisMonth(today: string): string[] {
  const dayOfMonth = fromDateKey(today).getDate()
  const log: string[] = []
  for (let ago = 0; ago < dayOfMonth; ago++) {
    if (ago % 4 !== 3) log.push(addDays(today, -ago))
  }
  return log
}

export function createDemoSubscriptions(today = todayKey()): Subscription[] {
  return [
    {
      // 今月よく使っている → 1回あたりが安い
      id: 'demo-video',
      name: '動画配信サービス',
      price: 1490,
      billingDay: dayOfMonthAfter(today, 10),
      trialEndDate: null,
      usageLog: [...frequentUsageThisMonth(today), addDays(today, -35), addDays(today, -40)],
      createdAt: addDays(today, -400),
    },
    {
      // 無料トライアル中（終了まで2日）
      id: 'demo-music',
      name: '音楽配信サービス',
      price: 1080,
      billingDay: dayOfMonthAfter(today, 2),
      trialEndDate: addDays(today, 2),
      usageLog: [addDays(today, -1), addDays(today, -6), addDays(today, -15)],
      createdAt: addDays(today, -28),
    },
    {
      // 3日後に請求
      id: 'demo-storage',
      name: 'クラウドストレージ',
      price: 400,
      billingDay: dayOfMonthAfter(today, 3),
      trialEndDate: null,
      usageLog: [addDays(today, -12), addDays(today, -27)],
      createdAt: addDays(today, -300),
    },
    {
      // 30日以上使っていない → 解約候補
      id: 'demo-news',
      name: 'ニュースアプリ',
      price: 980,
      billingDay: dayOfMonthAfter(today, 20),
      trialEndDate: null,
      usageLog: [addDays(today, -45), addDays(today, -60)],
      createdAt: addDays(today, -200),
    },
  ]
}

// ---- 保存データの読み込みと移行 ----

const DATE_KEY_PATTERN = /^\d{4}-\d{2}-\d{2}$/

function isDateKey(value: unknown): value is string {
  return typeof value === 'string' && DATE_KEY_PATTERN.test(value)
}

/** 旧形式（id / name / price のみ）のデータも、欠けた項目を初期値で補って読み込む */
export function migrateSubscription(raw: unknown, today: string): Subscription | null {
  if (typeof raw !== 'object' || raw === null) return null
  const item = raw as Record<string, unknown>
  const price = Number(item.price)
  if (typeof item.name !== 'string' || !Number.isFinite(price)) return null

  const billingDay = Number(item.billingDay)
  const usageLog = Array.isArray(item.usageLog) ? item.usageLog.filter(isDateKey) : []

  return {
    id: typeof item.id === 'string' ? item.id : crypto.randomUUID(),
    name: item.name,
    price,
    billingDay: Number.isInteger(billingDay) && billingDay >= 1 && billingDay <= 31 ? billingDay : 1,
    trialEndDate: isDateKey(item.trialEndDate) ? item.trialEndDate : null,
    usageLog: [...new Set(usageLog)],
    // 登録日が不明なものは移行日を登録日とする（移行直後に一斉に解約候補にならないように）
    createdAt: isDateKey(item.createdAt) ? item.createdAt : today,
  }
}

export function loadSubscriptions(): Subscription[] {
  const today = todayKey()
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed: unknown = JSON.parse(saved)
      if (Array.isArray(parsed)) {
        return parsed
          .map((raw) => migrateSubscription(raw, today))
          .filter((sub): sub is Subscription => sub !== null)
      }
    }
  } catch {
    // 読み込めない場合はデモデータで表示する
  }
  return createDemoSubscriptions(today)
}

export function saveSubscriptions(subscriptions: Subscription[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(subscriptions))
  } catch {
    // 保存できなくても画面上の操作は継続できる
  }
}
