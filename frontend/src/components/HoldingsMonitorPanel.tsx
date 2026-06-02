import { useCallback, useEffect, useState } from 'react';
import { deletePortfolioPosition, fetchPortfolioHoldings, putPortfolioPosition } from '../api';
import type { PortfolioHoldings } from '../types';

interface Props {
  onStockClick: (symbol: string) => void;
}

function pct(value: number | null | undefined, digits = 1): string {
  return value == null ? '-' : `${(value * 100).toFixed(digits)}%`;
}

function money(value: number | null | undefined): string {
  if (value == null) return '-';
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function statusClass(status: string | undefined): string {
  return (status || 'unknown').replace(/[^a-z0-9-]/gi, '-').toLowerCase();
}

export default function HoldingsMonitorPanel({ onStockClick }: Props) {
  const [data, setData] = useState<PortfolioHoldings | null>(null);
  const [symbol, setSymbol] = useState('');
  const [shares, setShares] = useState('');
  const [avgCost, setAvgCost] = useState('');
  const [thesis, setThesis] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    fetchPortfolioHoldings()
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Holdings unavailable'));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const resetForm = () => {
    setSymbol('');
    setShares('');
    setAvgCost('');
    setThesis('');
  };

  const save = async () => {
    const cleanSymbol = symbol.trim().toUpperCase();
    const shareValue = Number(shares);
    const costValue = avgCost.trim() ? Number(avgCost) : null;
    if (!cleanSymbol || !Number.isFinite(shareValue) || shareValue < 0) {
      setError('Enter a symbol and non-negative shares.');
      return;
    }
    if (costValue != null && (!Number.isFinite(costValue) || costValue < 0)) {
      setError('Average cost must be non-negative.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const result = await putPortfolioPosition(cleanSymbol, {
        shares: shareValue,
        avg_cost: costValue,
        thesis,
      });
      setData(result);
      resetForm();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Could not save holding');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (target: string) => {
    setSaving(true);
    setError('');
    try {
      setData(await deletePortfolioPosition(target));
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Could not delete holding');
    } finally {
      setSaving(false);
    }
  };

  const edit = (target: PortfolioHoldings['positions'][number]) => {
    setSymbol(target.symbol);
    setShares(String(target.shares ?? ''));
    setAvgCost(target.avg_cost == null ? '' : String(target.avg_cost));
    setThesis(target.thesis || '');
  };

  if (!data) {
    return (
      <div className="holdings-monitor">
        <div className="holdings-header">
          <span className="holdings-title">Holdings Monitor</span>
          <span className="holdings-muted">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`holdings-monitor holdings-${statusClass(data.status)}`}>
      <div className="holdings-header">
        <div>
          <span className="holdings-title">Holdings Monitor</span>
          <span className={`holdings-status ${statusClass(data.status)}`}>{data.label}</span>
        </div>
        <button className="holdings-refresh" onClick={load} disabled={saving}>Refresh</button>
      </div>

      <div className="holdings-message">{data.message}</div>
      {error && <div className="holdings-error">{error}</div>}

      <div className="holdings-summary">
        <span><strong>{data.summary.position_count}</strong> Positions</span>
        <span><strong>{money(data.summary.total_market_value)}</strong> Value</span>
        <span><strong>{money(data.summary.total_unrealized_pnl)}</strong> P/L</span>
        <span><strong>{pct(data.summary.estimated_stop_risk_pct)}</strong> Stop Risk</span>
        <span><strong>{data.summary.gate_blocked_positions}</strong> Gate Blocked</span>
      </div>

      <div className="holdings-form">
        <input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="Symbol" />
        <input value={shares} onChange={(event) => setShares(event.target.value)} placeholder="Shares" inputMode="decimal" />
        <input value={avgCost} onChange={(event) => setAvgCost(event.target.value)} placeholder="Avg cost" inputMode="decimal" />
        <input value={thesis} onChange={(event) => setThesis(event.target.value)} placeholder="Thesis" />
        <button onClick={save} disabled={saving}>{saving ? 'Saving' : 'Save'}</button>
      </div>

      <div className="holdings-table-wrap">
        <table className="holdings-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Value</th>
              <th>P/L</th>
              <th>Weight</th>
              <th>Risk</th>
              <th>Gate</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.positions.length === 0 ? (
              <tr>
                <td colSpan={7} className="holdings-empty">No holdings saved.</td>
              </tr>
            ) : data.positions.map((position) => (
              <tr key={position.symbol}>
                <td>
                  <button className="holdings-symbol" onClick={() => onStockClick(position.symbol)}>
                    {position.symbol}
                  </button>
                  <span className="holdings-mini">{position.shares} @ {money(position.latest_close)}</span>
                </td>
                <td>{money(position.market_value)}</td>
                <td className={(position.unrealized_pnl ?? 0) >= 0 ? 'up' : 'down'}>
                  {money(position.unrealized_pnl)}
                  <span>{pct(position.unrealized_pnl_pct)}</span>
                </td>
                <td>{pct(position.weight)}</td>
                <td>
                  <span>{money(position.estimated_stop_risk)}</span>
                  <em>{pct(position.stop_distance_pct)}</em>
                </td>
                <td>
                  <span className={`holdings-badge ${position.actionable_horizons.length ? 'candidate' : 'research-only'}`}>
                    {position.actionable_horizons.length ? position.actionable_horizons.join(', ').toUpperCase() : 'Blocked'}
                  </span>
                </td>
                <td className="holdings-actions">
                  <button onClick={() => edit(position)}>Edit</button>
                  <button onClick={() => remove(position.symbol)}>Del</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
