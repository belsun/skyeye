import { useEffect, useState } from 'react';
import { fetchTradeSetups } from '../api';
import type { TradeSetups, TradeSetupRow } from '../types';

interface Props {
  onStockClick: (symbol: string) => void;
}

const DEFAULT_CAPITAL = 100000;

function fmtMoney(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return '-';
  if (value >= 1000000) return `$${(value / 1000000).toFixed(2)}M`;
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`;
  return `$${value.toFixed(2)}`;
}

function fmtPrice(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return '-';
  return value >= 100 ? value.toFixed(2) : value.toFixed(3);
}

function fmtPct(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return '-';
  return `${(value * 100).toFixed(1)}%`;
}

function setupLabel(row: TradeSetupRow): string {
  if (row.setup_type === 'breakout') return '突破 / Breakout';
  if (row.setup_type === 'pullback') return '回踩 / Pullback';
  if (row.setup_type === 'risk-review') return '风险复盘 / Risk';
  return row.label;
}

export default function TradeSetupPanel({ onStockClick }: Props) {
  const [capital, setCapital] = useState(DEFAULT_CAPITAL);
  const [data, setData] = useState<TradeSetups | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    fetchTradeSetups(capital, 10)
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || '加载失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={`trade-setup trade-setup-${data?.status || 'loading'}`}>
      <div className="trade-setup-header">
        <div>
          <span className="trade-setup-title">
            <span className="zh-copy">交易价位研究</span>
            <span className="en-copy">Trade Setup Research</span>
          </span>
          {data && <span className={`trade-setup-status ${data.status}`}>{data.label}</span>}
          {loading && <span className="trade-setup-muted">更新中...</span>}
          {error && <span className="trade-setup-error">{error}</span>}
        </div>
        <div className="trade-setup-capital">
          <input
            type="number"
            min="0"
            step="10000"
            value={capital}
            onChange={(e) => setCapital(Number(e.target.value || DEFAULT_CAPITAL))}
            aria-label="Research capital"
          />
          <button onClick={load} disabled={loading}>刷新</button>
        </div>
      </div>

      {data && (
        <>
          <div className="trade-setup-message">{data.message}</div>
          <div className="trade-setup-summary">
            <span>候选 / Candidates<strong>{data.summary.candidates}</strong></span>
            <span>模拟 / Paper<strong>{data.summary.paper_watch}</strong></span>
            <span>回避 / Avoid<strong>{data.summary.avoid}</strong></span>
            <span>等待 / Wait<strong>{data.summary.wait}</strong></span>
            <span>Top<strong>{data.summary.top_symbol || '-'}</strong></span>
          </div>

          <div className="trade-setup-table-wrap">
            <table className="trade-setup-table">
              <thead>
                <tr>
                  <th>标的</th>
                  <th>结构</th>
                  <th>入场区</th>
                  <th>止损</th>
                  <th>目标</th>
                  <th>R/R</th>
                  <th>研究仓位</th>
                  <th>动作</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.symbol} className={row.status}>
                    <td>
                      <button className="trade-setup-symbol" onClick={() => onStockClick(row.symbol)}>
                        {row.symbol}
                      </button>
                      <span>{row.bias_label || row.decision_status || '-'}</span>
                    </td>
                    <td>
                      <strong>{setupLabel(row)}</strong>
                      <span>{row.latest_headline || row.message}</span>
                    </td>
                    <td>
                      <strong>{fmtPrice(row.entry_low)} - {fmtPrice(row.entry_high)}</strong>
                      <span>ATR {fmtPct(row.levels?.atr_pct)}</span>
                    </td>
                    <td className="down">{fmtPrice(row.stop_loss)}</td>
                    <td>
                      <strong className="up">{fmtPrice(row.target_1)}</strong>
                      <span>{fmtPrice(row.target_2)}</span>
                    </td>
                    <td>
                      <strong>{row.risk_reward_1 ?? '-'}</strong>
                      <span>{row.risk_reward_2 ?? '-'}</span>
                    </td>
                    <td>{fmtMoney(row.max_position_notional)}</td>
                    <td>
                      <span className={`trade-setup-badge ${row.status}`}>{row.label}</span>
                      <em>{row.action}</em>
                    </td>
                  </tr>
                ))}
                {data.rows.length === 0 && (
                  <tr><td colSpan={8} className="trade-setup-empty">暂无研究价位</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
