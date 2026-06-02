import { useEffect, useState } from 'react';
import { fetchRiskBrief } from '../api';
import type { RiskBrief } from '../types';

interface Props {
  symbol: string;
}

function pct(value: number | null | undefined): string {
  return value == null ? '-' : `${(value * 100).toFixed(1)}%`;
}

function currencyPrefix(symbol: string): string {
  if (symbol.endsWith('.HK')) return 'HK$';
  if (symbol.endsWith('.SS') || symbol.endsWith('.SZ')) return '¥';
  return '$';
}

export default function RiskBriefPanel({ symbol }: Props) {
  const [data, setData] = useState<RiskBrief | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!symbol) return;
    setError('');
    fetchRiskBrief(symbol)
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Risk brief unavailable'));
  }, [symbol]);

  if (error) {
    return (
      <div className="risk-brief">
        <div className="risk-brief-header">
          <span className="risk-brief-title">Risk Brief</span>
          <span className="risk-brief-error">{error}</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="risk-brief">
        <div className="risk-brief-header">
          <span className="risk-brief-title">Risk Brief</span>
          <span className="risk-brief-muted">Loading...</span>
        </div>
      </div>
    );
  }

  const budget = data.risk_budget;
  const prefix = currencyPrefix(data.symbol);
  const close = data.latest_close ?? null;
  const atr = close != null && data.atr_pct != null ? close * data.atr_pct : null;
  const support = close != null && atr != null ? close - atr * 1.2 : null;
  const stop = close != null && atr != null ? close - atr * 2 : null;
  const target = close != null && atr != null ? close + atr * ((data.trend_20d ?? 0) >= 0 ? 2.2 : 1.3) : null;
  const fmtMoney = (value: number | null | undefined) => value == null ? '-' : `${prefix}${value.toFixed(2)}`;

  return (
    <div className={`risk-brief risk-brief-${data.status}`}>
      <div className="risk-brief-header">
        <div>
          <span className="risk-brief-title">风险与价位 / Risk Brief</span>
          <span className="risk-brief-symbol">{data.symbol}</span>
        </div>
        <span className={`risk-brief-badge ${data.status}`}>{data.label}</span>
      </div>

      <div className="risk-brief-message">{data.message}</div>

      <div className="risk-brief-grid">
        <div className="risk-brief-stat">
          <span>最新收盘</span>
          <strong>{fmtMoney(data.latest_close)}</strong>
        </div>
        <div className="risk-brief-stat">
          <span>20日波动</span>
          <strong>{pct(data.annualized_volatility_20d)}</strong>
        </div>
        <div className="risk-brief-stat">
          <span>ATR 14</span>
          <strong>{pct(data.atr_pct)}</strong>
        </div>
        <div className="risk-brief-stat">
          <span>60日回撤</span>
          <strong className={(data.drawdown_60d ?? 0) < -0.15 ? 'down' : ''}>{pct(data.drawdown_60d)}</strong>
        </div>
        <div className="risk-brief-stat">
          <span>20日趋势</span>
          <strong className={(data.trend_20d ?? 0) >= 0 ? 'up' : 'down'}>{pct(data.trend_20d)}</strong>
        </div>
        <div className="risk-brief-stat">
          <span>仓位开关</span>
          <strong>{budget.position_sizing_enabled ? pct(budget.max_portfolio_risk_pct) : 'Off'}</strong>
        </div>
      </div>

      <div className="risk-price-plan">
        <div>
          <span>研究支撑</span>
          <strong>{fmtMoney(support)}</strong>
          <em>接近这里要看是否放量止跌</em>
        </div>
        <div>
          <span>止损参考</span>
          <strong>{fmtMoney(stop)}</strong>
          <em>跌破说明短线结构变弱</em>
        </div>
        <div>
          <span>目标参考</span>
          <strong>{fmtMoney(target)}</strong>
          <em>只用于 paper 复盘，不是实盘指令</em>
        </div>
      </div>

      <div className="risk-brief-gates">
        {Object.entries(data.predictions).map(([horizon, pred]) => (
          <div className="risk-brief-gate" key={horizon}>
            <span>{horizon.toUpperCase()}</span>
            <span>{pred.gate_label || pred.error || '-'}</span>
            {pred.failed_checks && pred.failed_checks.length > 0 && (
              <em>{pred.failed_checks.slice(0, 3).join(', ')}</em>
            )}
          </div>
        ))}
      </div>

      {data.notes.length > 0 && (
        <div className="risk-brief-notes">
          {data.notes.slice(0, 2).map((note) => (
            <span key={note}>{note}</span>
          ))}
        </div>
      )}
    </div>
  );
}
