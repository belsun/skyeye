import { useCallback, useEffect, useState } from 'react';
import { fetchTradeReview } from '../api';
import type { TradeReview } from '../types';

interface Props {
  onStockClick: (symbol: string) => void;
}

function money(value: number | null | undefined): string {
  if (value == null) return '-';
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function pct(value: number | null | undefined, digits = 0): string {
  return value == null ? '-' : `${(value * 100).toFixed(digits)}%`;
}

function statusClass(value: string | undefined): string {
  return (value || 'unknown').replace(/[^a-z0-9-]/gi, '-').toLowerCase();
}

export default function TradeReviewPanel({ onStockClick }: Props) {
  const [data, setData] = useState<TradeReview | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    fetchTradeReview()
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Trade review unavailable'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="trade-review">
        <div className="trade-review-header">
          <span className="trade-review-title">Trade Review</span>
          <span className="trade-review-error">{error}</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="trade-review">
        <div className="trade-review-header">
          <span className="trade-review-title">Trade Review</span>
          <span className="trade-review-muted">Loading...</span>
        </div>
      </div>
    );
  }

  const setups = data.setup_breakdown.slice(0, 5);
  const reviews = data.priority_reviews.slice(0, 4);

  return (
    <div className={`trade-review trade-review-${statusClass(data.status)}`}>
      <div className="trade-review-header">
        <div>
          <span className="trade-review-title">Trade Review</span>
          <span className={`trade-review-status ${statusClass(data.status)}`}>{data.label}</span>
        </div>
        <button className="trade-review-refresh" onClick={load} disabled={loading}>Refresh</button>
      </div>

      <div className="trade-review-message">{data.message}</div>

      <div className="trade-review-summary">
        <span><strong>{pct(data.summary.review_rate)}</strong> Review Rate</span>
        <span><strong>{money(data.summary.marked_pnl)}</strong> Marked P/L</span>
        <span><strong>{data.summary.gate_blocked_trades}</strong> Gate Blocks</span>
        <span><strong>{data.summary.setup_count}</strong> Setups</span>
      </div>

      <div className="trade-review-grid">
        <div className="trade-review-block">
          <div className="trade-review-block-title">Setup Playbook</div>
          {setups.length === 0 ? (
            <div className="trade-review-empty">No setup sample yet.</div>
          ) : (
            <div className="trade-review-setups">
              {setups.map((setup) => (
                <div className="trade-review-setup" key={setup.setup}>
                  <div>
                    <strong>{setup.setup}</strong>
                    <span>{setup.symbols.slice(0, 4).join(', ') || '-'}</span>
                  </div>
                  <div>
                    <em>{setup.trade_count} trades</em>
                    <span>{pct(setup.review_rate)} reviewed</span>
                  </div>
                  <div className={(setup.marked_pnl ?? 0) >= 0 ? 'up' : 'down'}>
                    <em>{money(setup.marked_pnl)}</em>
                    <span>{pct(setup.marked_pnl_pct, 1)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="trade-review-block">
          <div className="trade-review-block-title">Priority Reviews</div>
          {reviews.length === 0 ? (
            <div className="trade-review-empty">No review tasks.</div>
          ) : (
            <div className="trade-review-list">
              {reviews.map((item) => (
                <div className={`trade-review-item ${statusClass(item.priority)}`} key={item.id}>
                  <div className="trade-review-item-top">
                    <button className="trade-review-symbol" onClick={() => onStockClick(item.symbol)}>{item.symbol}</button>
                    <span className={`trade-review-priority ${statusClass(item.priority)}`}>{item.priority}</span>
                    <span>{item.trade_date}</span>
                  </div>
                  <div className="trade-review-action">{item.action}</div>
                  <div className="trade-review-evidence">
                    {(item.reasons.length ? item.reasons : [item.setup]).slice(0, 3).map((reason) => (
                      <span key={reason}>{reason}</span>
                    ))}
                    <span>{money(item.marked_pnl)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
