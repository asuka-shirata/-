import { useEffect, useState, type FormEvent } from 'react'

type Subscription = {
  id: string
  name: string
  price: number
}

const STORAGE_KEY = 'subscription-manager:items'

const DEMO_SUBSCRIPTIONS: Subscription[] = [
  { id: 'demo-1', name: '動画配信サービス', price: 1490 },
  { id: 'demo-2', name: '音楽配信サービス', price: 1080 },
  { id: 'demo-3', name: 'クラウドストレージ', price: 400 },
  { id: 'demo-4', name: 'ニュースアプリ', price: 980 },
]

const yen = new Intl.NumberFormat('ja-JP')

function loadSubscriptions(): Subscription[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return JSON.parse(saved) as Subscription[]
  } catch {
    // 読み込めない場合はデモデータで表示する
  }
  return DEMO_SUBSCRIPTIONS
}

function App() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>(loadSubscriptions)
  const [name, setName] = useState('')
  const [price, setPrice] = useState('')

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(subscriptions))
    } catch {
      // 保存できなくても画面上の操作は継続できる
    }
  }, [subscriptions])

  const total = subscriptions.reduce((sum, sub) => sum + sub.price, 0)
  const priceValue = Number(price)
  const canAdd = name.trim() !== '' && price !== '' && priceValue >= 0

  function addSubscription(e: FormEvent) {
    e.preventDefault()
    if (!canAdd) return
    setSubscriptions((prev) => [
      ...prev,
      { id: crypto.randomUUID(), name: name.trim(), price: Math.round(priceValue) },
    ])
    setName('')
    setPrice('')
  }

  function deleteSubscription(id: string) {
    setSubscriptions((prev) => prev.filter((sub) => sub.id !== id))
  }

  function resetDemo() {
    setSubscriptions(DEMO_SUBSCRIPTIONS)
  }

  return (
    <div className="app">
      <header className="header">
        <h1 className="app-title">サブスク管理</h1>
      </header>

      <section className="total-card" aria-live="polite">
        <p className="total-label">毎月の支払い合計</p>
        <p className="total-amount">
          <span className="total-currency">¥</span>
          {yen.format(total)}
        </p>
        <p className="total-sub">
          年間 ¥{yen.format(total * 12)} ・ {subscriptions.length}件のサブスク
        </p>
      </section>

      <section className="card">
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
          <button className="add-btn" type="submit" disabled={!canAdd}>
            追加する
          </button>
        </form>
      </section>

      <section className="card">
        <div className="list-header">
          <h2 className="section-title">登録中のサブスク</h2>
          <button className="text-btn" type="button" onClick={resetDemo}>
            デモデータに戻す
          </button>
        </div>

        {subscriptions.length === 0 ? (
          <p className="empty">まだ登録がありません。上のフォームから追加してください。</p>
        ) : (
          <ul className="list">
            {subscriptions.map((sub) => (
              <li key={sub.id} className="list-item">
                <div className="item-main">
                  <span className="item-name">{sub.name}</span>
                  <span className="item-price">¥{yen.format(sub.price)}<small> / 月</small></span>
                </div>
                <button
                  className="delete-btn"
                  type="button"
                  onClick={() => deleteSubscription(sub.id)}
                  aria-label={`${sub.name}を削除`}
                >
                  削除
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

export default App
