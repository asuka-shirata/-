import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  SOON_DAYS,
  UPCOMING_DAYS,
  costPerUse,
  createDemoSubscriptions,
  daysBetween,
  formatMonthDay,
  isCancelCandidate,
  isTrialActive,
  lastUsedDate,
  loadSubscriptions,
  nextChargeDate,
  saveSubscriptions,
  todayKey,
  usageThisMonth,
  type Subscription,
} from './subscriptions'

const NOTIFIED_KEY = 'subscription-manager:notified-on'
const DAY_OPTIONS = Array.from({ length: 31 }, (_, i) => i + 1)

const yen = new Intl.NumberFormat('ja-JP')

type Alert = {
  id: string
  tone: 'gold' | 'danger'
  text: string
}

type NotifyState = NotificationPermission | 'unsupported'

function getNotifyState(): NotifyState {
  return typeof window !== 'undefined' && 'Notification' in window
    ? Notification.permission
    : 'unsupported'
}

function relativeDayLabel(days: number): string {
  if (days === 0) return '本日'
  if (days === 1) return '明日'
  return `${days}日後`
}

/** 3日以内の請求とトライアル終了をまとめる */
function collectAlerts(subscriptions: Subscription[], today: string): Alert[] {
  const alerts: Alert[] = []
  for (const sub of subscriptions) {
    const chargeDate = nextChargeDate(sub, today)
    const days = daysBetween(today, chargeDate)
    if (days > SOON_DAYS) continue
    const when = days === 0 ? '本日' : `${relativeDayLabel(days)}（${formatMonthDay(chargeDate)}）`
    if (isTrialActive(sub, today)) {
      alerts.push({
        id: sub.id,
        tone: 'danger',
        text:
          days === 0
            ? `${sub.name}の無料トライアルは本日で終了。月額 ¥${yen.format(sub.price)} の課金が始まります`
            : `${sub.name}の無料トライアルがあと${days}日で終了。${formatMonthDay(chargeDate)}から月額 ¥${yen.format(sub.price)} が課金されます`,
      })
    } else {
      alerts.push({
        id: sub.id,
        tone: 'gold',
        text: `${sub.name} ¥${yen.format(sub.price)} の引き落としが${when}`,
      })
    }
  }
  return alerts.sort((a, b) => (a.tone === b.tone ? 0 : a.tone === 'danger' ? -1 : 1))
}

function showBrowserNotification(alerts: Alert[]): void {
  if (alerts.length === 0 || getNotifyState() !== 'granted') return
  try {
    new Notification('サブスク管理：直近のお知らせ', {
      body: alerts.map((alert) => alert.text).join('\n'),
    })
    localStorage.setItem(NOTIFIED_KEY, todayKey())
  } catch {
    // 通知が使えない環境でもアプリの動作は続ける
  }
}

// ---- アイコン（ゴールドは数カ所に限定） ----

function BellIcon() {
  return (
    <svg className="icon icon-gold" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 10a6 6 0 1 1 12 0c0 4.5 1.8 6.2 2.5 7H3.5c.7-.8 2.5-2.5 2.5-7Z" />
      <path d="M10 20a2.2 2.2 0 0 0 4 0" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="icon icon-positive" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12.4 2.7 2.6L16 9.5" />
    </svg>
  )
}

// ---- 画面パーツ ----

function NoticeBanner({ alerts, onClose }: { alerts: Alert[]; onClose: () => void }) {
  return (
    <section className="notice" role="status">
      <div className="notice-head">
        <BellIcon />
        <span className="eyebrow">お知らせ</span>
        <button className="notice-close" type="button" onClick={onClose} aria-label="お知らせを閉じる">
          閉じる
        </button>
      </div>
      <ul className="notice-list">
        {alerts.map((alert) => (
          <li key={alert.id} className={`notice-item notice-${alert.tone}`}>
            {alert.text}
          </li>
        ))}
      </ul>
    </section>
  )
}

function DiagnosisCard({ candidates, today }: { candidates: Subscription[]; today: string }) {
  const yearlySaving = candidates.reduce((sum, sub) => sum + sub.price * 12, 0)

  return (
    <section className="card">
      <p className="eyebrow">無駄サブスク診断</p>
      {candidates.length === 0 ? (
        <div className="diagnosis-ok">
          <CheckIcon />
          <div>
            <p className="diagnosis-ok-title">無駄なサブスクはありません</p>
            <p className="muted-text">どのサブスクも直近30日以内に使っています。</p>
          </div>
        </div>
      ) : (
        <>
          <p className="saving-prefix">解約候補をすべて解約すると、年間</p>
          <p className="saving">
            <span className="saving-amount">¥{yen.format(yearlySaving)}</span>
            <span className="saving-suffix">浮きます</span>
          </p>
          <p className="muted-text">直近30日で一度も使っていないサブスクが{candidates.length}件あります。</p>
          <ul className="candidate-list">
            {candidates.map((sub) => {
              const last = lastUsedDate(sub)
              return (
                <li key={sub.id} className="candidate-item">
                  <div className="candidate-main">
                    <span className="candidate-name">{sub.name}</span>
                    <span className="candidate-note">
                      {last ? `最終利用 ${daysBetween(last, today)}日前` : '利用記録なし'}
                    </span>
                  </div>
                  <span className="num">¥{yen.format(sub.price)}<small> / 月</small></span>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </section>
  )
}

function UpcomingCard({
  subscriptions,
  today,
  notifyState,
  onEnableNotify,
}: {
  subscriptions: Subscription[]
  today: string
  notifyState: NotifyState
  onEnableNotify: () => void
}) {
  const upcoming = subscriptions
    .map((sub) => ({ sub, date: nextChargeDate(sub, today) }))
    .map((entry) => ({ ...entry, days: daysBetween(today, entry.date) }))
    .filter((entry) => entry.days <= UPCOMING_DAYS)
    .sort((a, b) => a.days - b.days)

  return (
    <section className="card">
      <h2 className="section-title">直近の引き落とし</h2>
      <p className="muted-text section-lead">14日以内の請求予定</p>

      {upcoming.length === 0 ? (
        <p className="empty">14日以内の引き落としはありません。</p>
      ) : (
        <ul className="upcoming-list">
          {upcoming.map(({ sub, date, days }) => (
            <li key={sub.id} className="upcoming-item">
              <span className={days <= SOON_DAYS ? 'badge badge-gold' : 'upcoming-when'}>
                {relativeDayLabel(days)}
              </span>
              <span className="upcoming-name">
                {sub.name}
                <span className="upcoming-date">
                  {formatMonthDay(date)}
                  {isTrialActive(sub, today) && ' ・ トライアル終了後の初回'}
                </span>
              </span>
              <span className="num">¥{yen.format(sub.price)}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="notify-row">
        {notifyState === 'default' && (
          <button className="ghost-btn" type="button" onClick={onEnableNotify}>
            <BellIcon />
            請求日をブラウザ通知で受け取る
          </button>
        )}
        {notifyState === 'granted' && <p className="muted-text">ブラウザ通知：オン（3日以内の請求をお知らせします）</p>}
        {notifyState === 'denied' && (
          <p className="muted-text">ブラウザ通知はオフです。画面上のお知らせは引き続き表示されます。</p>
        )}
        {notifyState === 'unsupported' && (
          <p className="muted-text">このブラウザはブラウザ通知に対応していません。</p>
        )}
      </div>
    </section>
  )
}

function SubscriptionItem({
  sub,
  today,
  isCandidate,
  onUse,
  onUndoUse,
  onDelete,
}: {
  sub: Subscription
  today: string
  isCandidate: boolean
  onUse: () => void
  onUndoUse: () => void
  onDelete: () => void
}) {
  const chargeDate = nextChargeDate(sub, today)
  const days = daysBetween(today, chargeDate)
  const trialActive = isTrialActive(sub, today)
  const trialDaysLeft = sub.trialEndDate ? daysBetween(today, sub.trialEndDate) : null
  const count = usageThisMonth(sub, today)
  const perUse = costPerUse(sub, today)
  const usedToday = sub.usageLog.includes(today)

  return (
    <li className="sub-item">
      <div className="sub-top">
        <div className="sub-title">
          <span className="item-name">{sub.name}</span>
          {isCandidate && <span className="badge badge-danger">解約候補</span>}
          {trialActive && <span className="badge badge-muted">トライアル中</span>}
        </div>
        <span className="item-price">
          ¥{yen.format(sub.price)}
          <small>/ 月</small>
        </span>
      </div>

      <div className="sub-meta">
        <p className="meta-line">
          {days === 0 ? (
            <>
              <span className="badge badge-gold">本日</span>
              {trialActive ? '初回請求' : '請求日'}（{formatMonthDay(chargeDate)}）
            </>
          ) : (
            <>
              {trialActive ? '初回請求まで' : '次回請求まで'}
              {days <= SOON_DAYS ? (
                <span className="badge badge-gold">あと{days}日</span>
              ) : (
                <span className="num">あと{days}日</span>
              )}
              （{formatMonthDay(chargeDate)}）
            </>
          )}
        </p>

        {sub.trialEndDate && trialDaysLeft !== null && (
          <p className={`meta-line ${trialActive && trialDaysLeft <= SOON_DAYS ? 'text-danger' : ''}`}>
            {!trialActive
              ? '無料トライアルは終了しました（課金中）'
              : trialDaysLeft === 0
                ? `トライアルは本日で終了。本日から月額 ¥${yen.format(sub.price)} が課金されます`
                : trialDaysLeft <= SOON_DAYS
                  ? `トライアルがあと${trialDaysLeft}日で終了。${formatMonthDay(sub.trialEndDate)}以降は月額 ¥${yen.format(sub.price)} が課金されます`
                  : `無料トライアル中（${formatMonthDay(sub.trialEndDate)}まで。以降は課金されます）`}
          </p>
        )}

        <p className="meta-line">
          {perUse === null ? (
            <span className="muted-text">今月は未使用</span>
          ) : (
            <>
              今月 <span className="num">{count}回</span>
              <span className="dot">・</span>
              1回あたり <span className="num strong">¥{yen.format(perUse)}</span>
              {perUse <= sub.price / 2 && <span className="badge badge-positive">元が取れています</span>}
            </>
          )}
        </p>
      </div>

      <div className="sub-actions">
        {usedToday ? (
          <div className="used-today">
            <span className="used-label">
              <CheckIcon />
              今日使用済み
            </span>
            <button className="text-btn" type="button" onClick={onUndoUse}>
              取り消す
            </button>
          </div>
        ) : (
          <button className="use-btn" type="button" onClick={onUse}>
            今日使った
          </button>
        )}
        <button className="delete-btn" type="button" onClick={onDelete} aria-label={`${sub.name}を削除`}>
          削除
        </button>
      </div>
    </li>
  )
}

function App() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>(loadSubscriptions)
  const [name, setName] = useState('')
  const [price, setPrice] = useState('')
  const [billingDay, setBillingDay] = useState(() => new Date().getDate())
  const [isTrial, setIsTrial] = useState(false)
  const [trialEndDate, setTrialEndDate] = useState('')
  const [notifyState, setNotifyState] = useState<NotifyState>(getNotifyState)
  const [noticeOpen, setNoticeOpen] = useState(true)
  const formRef = useRef<HTMLElement>(null)

  const today = todayKey()
  // お知らせはページを開いた時点の内容で表示する
  const [initialAlerts] = useState(() => collectAlerts(subscriptions, today))

  useEffect(() => {
    saveSubscriptions(subscriptions)
  }, [subscriptions])

  // 通知を許可済みなら、1日1回だけブラウザ通知を出す
  useEffect(() => {
    try {
      if (localStorage.getItem(NOTIFIED_KEY) === todayKey()) return
    } catch {
      return
    }
    showBrowserNotification(initialAlerts)
  }, [initialAlerts])

  const total = subscriptions.reduce((sum, sub) => sum + sub.price, 0)
  const candidates = subscriptions.filter((sub) => isCancelCandidate(sub, today))
  const priceValue = Number(price)
  const canAdd = name.trim() !== '' && price !== '' && priceValue >= 0 && (!isTrial || trialEndDate !== '')

  function addSubscription(e: FormEvent) {
    e.preventDefault()
    if (!canAdd) return
    setSubscriptions((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        name: name.trim(),
        price: Math.round(priceValue),
        billingDay,
        trialEndDate: isTrial ? trialEndDate : null,
        usageLog: [],
        createdAt: todayKey(),
      },
    ])
    setName('')
    setPrice('')
    setIsTrial(false)
    setTrialEndDate('')
  }

  function deleteSubscription(id: string) {
    setSubscriptions((prev) => prev.filter((sub) => sub.id !== id))
  }

  function logUsage(id: string) {
    const day = todayKey()
    setSubscriptions((prev) =>
      prev.map((sub) =>
        sub.id === id && !sub.usageLog.includes(day) ? { ...sub, usageLog: [...sub.usageLog, day] } : sub,
      ),
    )
  }

  function undoUsage(id: string) {
    const day = todayKey()
    setSubscriptions((prev) =>
      prev.map((sub) => (sub.id === id ? { ...sub, usageLog: sub.usageLog.filter((d) => d !== day) } : sub)),
    )
  }

  function resetDemo() {
    setSubscriptions(createDemoSubscriptions())
  }

  async function enableNotify() {
    try {
      const permission = await Notification.requestPermission()
      setNotifyState(permission)
      if (permission === 'granted') showBrowserNotification(collectAlerts(subscriptions, todayKey()))
    } catch {
      setNotifyState(getNotifyState())
    }
  }

  function scrollToForm() {
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="app">
      <header className="header">
        <h1 className="app-title">サブスク管理</h1>
      </header>

      {noticeOpen && initialAlerts.length > 0 && (
        <NoticeBanner alerts={initialAlerts} onClose={() => setNoticeOpen(false)} />
      )}

      <section className="total-card" aria-live="polite">
        <p className="total-label">毎月の支払い合計</p>
        <p className="total-amount">
          <span className="total-currency">¥</span>
          <span className="total-number">{yen.format(total)}</span>
        </p>
        <p className="total-sub">
          年間 ¥{yen.format(total * 12)} ・ {subscriptions.length}件のサブスク
        </p>
      </section>

      <DiagnosisCard candidates={candidates} today={today} />

      <UpcomingCard
        subscriptions={subscriptions}
        today={today}
        notifyState={notifyState}
        onEnableNotify={enableNotify}
      />

      <section className="card">
        <div className="list-header">
          <h2 className="section-title">登録中のサブスク</h2>
          <button className="text-btn" type="button" onClick={scrollToForm}>
            ＋ 追加
          </button>
        </div>

        {subscriptions.length === 0 ? (
          <p className="empty">まだ登録がありません。下のフォームから追加してください。</p>
        ) : (
          <ul className="list">
            {subscriptions.map((sub) => (
              <SubscriptionItem
                key={sub.id}
                sub={sub}
                today={today}
                isCandidate={candidates.includes(sub)}
                onUse={() => logUsage(sub.id)}
                onUndoUse={() => undoUsage(sub.id)}
                onDelete={() => deleteSubscription(sub.id)}
              />
            ))}
          </ul>
        )}

        <div className="list-footer">
          <button className="text-btn" type="button" onClick={resetDemo}>
            デモデータに戻す
          </button>
        </div>
      </section>

      <section className="card" ref={formRef}>
        <h2 className="section-title">サブスクを追加</h2>
        <form className="add-form" onSubmit={addSubscription}>
          <label className="field">
            <span className="field-label">サービス名</span>
            <input
              className="input"
              type="text"
              placeholder="例: 動画配信サービス"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <div className="field-row">
            <label className="field">
              <span className="field-label">月額料金（円）</span>
              <input
                className="input"
                type="number"
                inputMode="numeric"
                min="0"
                placeholder="例: 1490"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
              />
            </label>
            <label className="field">
              <span className="field-label">請求日（毎月）</span>
              <select className="input" value={billingDay} onChange={(e) => setBillingDay(Number(e.target.value))}>
                {DAY_OPTIONS.map((day) => (
                  <option key={day} value={day}>
                    {day}日
                  </option>
                ))}
              </select>
            </label>
          </div>
          {billingDay > 28 && <p className="field-hint">月末を超える月は、その月の末日に請求として計算します。</p>}

          <label className="toggle">
            <input
              className="toggle-input"
              type="checkbox"
              role="switch"
              checked={isTrial}
              onChange={(e) => setIsTrial(e.target.checked)}
            />
            <span className="toggle-track" aria-hidden="true" />
            <span>無料トライアル中</span>
          </label>

          {isTrial && (
            <label className="field">
              <span className="field-label">トライアル終了日</span>
              <input
                className="input"
                type="date"
                min={today}
                value={trialEndDate}
                onChange={(e) => setTrialEndDate(e.target.value)}
              />
            </label>
          )}

          <button className="add-btn" type="submit" disabled={!canAdd}>
            追加する
          </button>
        </form>
      </section>
    </div>
  )
}

export default App
