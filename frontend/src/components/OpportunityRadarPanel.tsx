import { useEffect, useMemo, useState } from 'react';
import { fetchOpportunityRadar, fetchPaperBookPerformance, fetchPaperBooks, postPaperOrder } from '../api';
import type { EligiblePaperSymbol, OpportunityAlert, OpportunityRadar, PaperBook, PaperBookPerformance } from '../types';

type MarketFilter = 'all' | 'hk' | 'us';
type BookId = 'hkd' | 'usd';

interface Props {
  onStockClick: (symbol: string) => void;
  defaultMarket?: MarketFilter;
}

function money(value?: number | null, currency?: string): string {
  if (value == null || Number.isNaN(value)) return '-';
  const prefix = currency === 'HKD' ? 'HK$' : '$';
  return `${prefix}${Math.round(value).toLocaleString()}`;
}

function pct(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return '-';
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`;
}

function levelText(level: string): string {
  return level === 'strong' ? '强信号' : '观察';
}

function bookCurrency(bookId: BookId): 'HKD' | 'USD' {
  return bookId === 'hkd' ? 'HKD' : 'USD';
}

export default function OpportunityRadarPanel({ onStockClick, defaultMarket = 'all' }: Props) {
  const [market, setMarket] = useState<MarketFilter>(defaultMarket);
  const [radar, setRadar] = useState<OpportunityRadar | null>(null);
  const [books, setBooks] = useState<PaperBook[]>([]);
  const [performance, setPerformance] = useState<Partial<Record<BookId, PaperBookPerformance>>>({});
  const [selectedTheme, setSelectedTheme] = useState<string>('all');
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [orderBusy, setOrderBusy] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    Promise.all([
      fetchOpportunityRadar(market, 10),
      fetchPaperBooks(),
      fetchPaperBookPerformance('hkd', 20),
      fetchPaperBookPerformance('usd', 20),
    ])
      .then(([radarData, bookData, hkdPerf, usdPerf]) => {
        setRadar(radarData);
        setBooks(bookData.books);
        setPerformance({ hkd: hkdPerf, usd: usdPerf });
        setSelectedAlertId((current) => current || radarData.alerts[0]?.id || null);
      })
      .catch((err) => setError(err?.response?.data?.detail || err.message || '风口雷达加载失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [market]);

  useEffect(() => {
    setMarket(defaultMarket);
  }, [defaultMarket]);

  const alerts = useMemo(() => {
    const rows = radar?.alerts || [];
    return selectedTheme === 'all' ? rows : rows.filter((item) => item.theme === selectedTheme);
  }, [radar, selectedTheme]);

  const selectedAlert = useMemo(() => {
    return radar?.alerts.find((item) => item.id === selectedAlertId) || alerts[0] || null;
  }, [radar, selectedAlertId, alerts]);

  async function placeOrder(alert: OpportunityAlert, option: EligiblePaperSymbol) {
    const key = `${alert.id}:${option.book_id}:${option.symbol}`;
    setOrderBusy(key);
    setMessage('');
    setError('');
    try {
      await postPaperOrder({
        book_id: option.book_id,
        symbol: option.symbol,
        side: 'buy',
        notional: option.notional,
        reason: `Opportunity Radar: ${alert.theme_label}`,
        radar_alert_id: alert.id,
      });
      const [bookData, hkdPerf, usdPerf] = await Promise.all([
        fetchPaperBooks(),
        fetchPaperBookPerformance('hkd', 20),
        fetchPaperBookPerformance('usd', 20),
      ]);
      setBooks(bookData.books);
      setPerformance({ hkd: hkdPerf, usd: usdPerf });
      setMessage(`已加入 ${option.book_id.toUpperCase()} 模拟账本：${option.symbol}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || '模拟交易失败');
    } finally {
      setOrderBusy(null);
    }
  }

  return (
    <div className="opportunity-radar">
      <div className="opportunity-header">
        <div>
          <span className="opportunity-title">
            <span className="zh-copy">风口雷达</span>
            <span className="en-copy">Opportunity Radar</span>
          </span>
          {radar && <span className="opportunity-status">{radar.summary.strong} 强信号 · {radar.summary.watch} 观察</span>}
          {loading && <span className="opportunity-muted">更新中...</span>}
        </div>
        <div className="opportunity-actions">
          <div className="opportunity-market-tabs">
            {(['all', 'hk', 'us'] as MarketFilter[]).map((item) => (
              <button key={item} className={market === item ? 'active' : ''} onClick={() => setMarket(item)}>
                {item.toUpperCase()}
              </button>
            ))}
          </div>
          <button className="opportunity-refresh" onClick={load} disabled={loading}>刷新</button>
        </div>
      </div>

      <div className="opportunity-message">
        平衡探索模式：把新闻、重大事件、IPO、产业链、催化和价位研究合并成 paper-only 机会队列。
      </div>
      {message && <div className="opportunity-ok">{message}</div>}
      {error && <div className="opportunity-error">{error}</div>}

      {radar && (
        <>
          <div className="opportunity-summary">
            <span>主题 / Themes<strong>{radar.summary.themes}</strong></span>
            <span>信号 / Alerts<strong>{radar.summary.alerts}</strong></span>
            <span>强信号<strong>{radar.summary.strong}</strong></span>
            <span>可模拟标的<strong>{radar.summary.paper_eligible_symbols}</strong></span>
            <span>Top Score<strong>{radar.summary.top_score ?? '-'}</strong></span>
          </div>

          <div className="paper-book-strip">
            {books.map((book) => {
              const perf = performance[book.id];
              return (
                <div key={book.id} className="paper-book-card">
                  <span>{book.label}</span>
                  <strong>{money(book.equity, book.currency)}</strong>
                  <em>Cash {money(book.cash, book.currency)} · {pct(perf?.summary.window_return)}</em>
                </div>
              );
            })}
          </div>

          <div className="opportunity-theme-tabs">
            <button className={selectedTheme === 'all' ? 'active' : ''} onClick={() => setSelectedTheme('all')}>全部</button>
            {radar.themes.map((theme) => (
              <button
                key={theme.key}
                className={selectedTheme === theme.key ? 'active' : ''}
                onClick={() => setSelectedTheme(theme.key)}
              >
                {theme.label}
                <span>{theme.top_score}</span>
              </button>
            ))}
          </div>

          <div className="opportunity-grid">
            <div className="opportunity-alerts">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`opportunity-alert ${alert.signal_level} ${selectedAlert?.id === alert.id ? 'active' : ''}`}
                  onClick={() => setSelectedAlertId(alert.id)}
                >
                  <div className="opportunity-alert-top">
                    <span className={`opportunity-level ${alert.signal_level}`}>{levelText(alert.signal_level)}</span>
                    <strong>{alert.score}</strong>
                  </div>
                  <h3>{alert.theme_label}</h3>
                  <p>{alert.title}</p>
                  <div className="opportunity-symbols">
                    {alert.primary_symbols.slice(0, 6).map((symbol) => (
                      <button key={symbol} onClick={(e) => { e.stopPropagation(); onStockClick(symbol); }}>{symbol}</button>
                    ))}
                  </div>
                  <div className="opportunity-paper-row">
                    {alert.eligible_paper_symbols.length > 0 ? alert.eligible_paper_symbols.slice(0, 3).map((option) => {
                      const key = `${alert.id}:${option.book_id}:${option.symbol}`;
                      return (
                        <button
                          key={key}
                          disabled={orderBusy === key}
                          onClick={(e) => { e.stopPropagation(); placeOrder(alert, option); }}
                        >
                          {orderBusy === key ? '加入中...' : `模拟 ${option.symbol} ${money(option.notional, bookCurrency(option.book_id))}`}
                        </button>
                      );
                    }) : <span>仅观察</span>}
                  </div>
                </div>
              ))}
              {alerts.length === 0 && <div className="opportunity-empty">暂无风口信号</div>}
            </div>

            <div className="opportunity-detail">
              {selectedAlert ? (
                <>
                  <div className="opportunity-detail-head">
                    <span className={`opportunity-level ${selectedAlert.signal_level}`}>{levelText(selectedAlert.signal_level)}</span>
                    <strong>{selectedAlert.score}</strong>
                  </div>
                  <h3>{selectedAlert.title}</h3>
                  <p>{selectedAlert.thesis}</p>
                  <div className="opportunity-score-grid">
                    {Object.entries(selectedAlert.score_components).map(([key, value]) => (
                      <span key={key}>{key}<strong>{value ?? '-'}</strong></span>
                    ))}
                  </div>
                  <div className="opportunity-detail-title">证据 / Evidence</div>
                  <div className="opportunity-evidence">
                    {selectedAlert.evidence.map((item, i) => (
                      <a key={`${item.title}-${i}`} href={item.url || undefined} target="_blank" rel="noreferrer">
                        <span>{item.type} · {item.source}</span>
                        <strong>{item.title}</strong>
                      </a>
                    ))}
                  </div>
                  <div className="opportunity-detail-title">风险 / Risks</div>
                  <div className="opportunity-risks">
                    {selectedAlert.risks.map((risk) => <span key={risk}>{risk}</span>)}
                  </div>
                </>
              ) : (
                <div className="opportunity-empty">选择一个信号查看证据</div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
