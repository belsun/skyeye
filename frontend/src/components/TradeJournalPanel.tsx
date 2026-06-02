import { useCallback, useEffect, useState } from 'react';
import { deleteTradeJournalEntry, fetchTradeJournal, postTradeJournalEntry, putTradeJournalEntry } from '../api';
import type { TradeJournal, TradeJournalEntry, TradeJournalInput } from '../types';

interface Props {
  onStockClick: (symbol: string) => void;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function money(value: number | null | undefined): string {
  if (value == null) return '-';
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function pct(value: number | null | undefined, digits = 1): string {
  return value == null ? '-' : `${(value * 100).toFixed(digits)}%`;
}

function statusClass(value: string | undefined): string {
  return (value || 'unknown').replace(/[^a-z0-9-]/gi, '-').toLowerCase();
}

const emptyDraft: TradeJournalInput = {
  symbol: '',
  side: 'buy',
  quantity: 0,
  price: 0,
  trade_date: today(),
  thesis: '',
  setup: '',
  review: '',
};

export default function TradeJournalPanel({ onStockClick }: Props) {
  const [data, setData] = useState<TradeJournal | null>(null);
  const [draft, setDraft] = useState<TradeJournalInput>(emptyDraft);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    fetchTradeJournal()
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Trade journal unavailable'));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const setField = (key: keyof TradeJournalInput, value: string) => {
    setDraft((current) => ({
      ...current,
      [key]: key === 'quantity' || key === 'price' ? Number(value) : value,
    }));
  };

  const reset = () => {
    setDraft({ ...emptyDraft, trade_date: today() });
    setEditingId(null);
  };

  const save = async () => {
    const symbol = draft.symbol.trim().toUpperCase();
    if (!symbol || !draft.quantity || !draft.price) {
      setError('Enter symbol, quantity, and price.');
      return;
    }
    const payload = { ...draft, symbol };
    setSaving(true);
    setError('');
    try {
      const result = editingId
        ? await putTradeJournalEntry(editingId, payload)
        : await postTradeJournalEntry(payload);
      setData(result);
      reset();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Could not save trade');
    } finally {
      setSaving(false);
    }
  };

  const edit = (trade: TradeJournalEntry) => {
    setEditingId(trade.id);
    setDraft({
      symbol: trade.symbol,
      side: trade.side,
      quantity: trade.quantity,
      price: trade.price,
      trade_date: trade.trade_date,
      thesis: trade.thesis,
      setup: trade.setup,
      review: trade.review,
    });
  };

  const remove = async (tradeId: number) => {
    setSaving(true);
    setError('');
    try {
      setData(await deleteTradeJournalEntry(tradeId));
      if (editingId === tradeId) reset();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Could not delete trade');
    } finally {
      setSaving(false);
    }
  };

  if (!data) {
    return (
      <div className="trade-journal">
        <div className="trade-journal-header">
          <span className="trade-journal-title">Trade Journal</span>
          <span className={error ? 'trade-journal-error' : 'trade-journal-muted'}>
            {error || 'Loading...'}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className={`trade-journal trade-journal-${statusClass(data.status)}`}>
      <div className="trade-journal-header">
        <div>
          <span className="trade-journal-title">Trade Journal</span>
          <span className={`trade-journal-status ${statusClass(data.status)}`}>{data.label}</span>
        </div>
        <button className="trade-journal-refresh" onClick={load} disabled={saving}>Refresh</button>
      </div>

      <div className="trade-journal-message">{data.message}</div>
      {error && <div className="trade-journal-error">{error}</div>}

      <div className="trade-journal-summary">
        <span><strong>{data.summary.trade_count}</strong> Trades</span>
        <span><strong>{money(data.summary.total_notional)}</strong> Notional</span>
        <span><strong>{money(data.summary.marked_pnl)}</strong> Marked P/L</span>
        <span><strong>{data.summary.missing_review}</strong> Need Review</span>
      </div>

      <div className="trade-journal-form">
        <input value={draft.symbol} onChange={(e) => setField('symbol', e.target.value)} placeholder="Symbol" />
        <select value={draft.side} onChange={(e) => setField('side', e.target.value)}>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
        <input value={draft.quantity || ''} onChange={(e) => setField('quantity', e.target.value)} placeholder="Qty" inputMode="decimal" />
        <input value={draft.price || ''} onChange={(e) => setField('price', e.target.value)} placeholder="Price" inputMode="decimal" />
        <input value={draft.trade_date || ''} onChange={(e) => setField('trade_date', e.target.value)} placeholder="YYYY-MM-DD" type="date" />
        <input value={draft.setup || ''} onChange={(e) => setField('setup', e.target.value)} placeholder="Setup" />
        <input value={draft.thesis || ''} onChange={(e) => setField('thesis', e.target.value)} placeholder="Thesis" />
        <input value={draft.review || ''} onChange={(e) => setField('review', e.target.value)} placeholder="Review" />
        <button onClick={save} disabled={saving}>{editingId ? 'Update' : 'Log'}</button>
        {editingId && <button onClick={reset} disabled={saving}>Cancel</button>}
      </div>

      <div className="trade-journal-table-wrap">
        <table className="trade-journal-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Notional</th>
              <th>Marked P/L</th>
              <th>Gate</th>
              <th>Review</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.trades.length === 0 ? (
              <tr><td className="trade-journal-empty" colSpan={8}>No trades logged.</td></tr>
            ) : data.trades.slice(0, 8).map((trade) => (
              <tr key={trade.id}>
                <td>{trade.trade_date}</td>
                <td>
                  <button className="trade-journal-symbol" onClick={() => onStockClick(trade.symbol)}>{trade.symbol}</button>
                  <span>{trade.quantity} @ {money(trade.price)}</span>
                </td>
                <td><span className={`trade-side ${trade.side}`}>{trade.side}</span></td>
                <td>{money(trade.entry_notional)}</td>
                <td className={(trade.marked_pnl ?? 0) >= 0 ? 'up' : 'down'}>
                  {money(trade.marked_pnl)}
                  <span>{pct(trade.marked_pnl_pct)}</span>
                </td>
                <td>
                  <span className={`trade-gate ${trade.actionable_horizons.length ? 'candidate' : 'blocked'}`}>
                    {trade.actionable_horizons.length ? trade.actionable_horizons.join(', ').toUpperCase() : 'Blocked'}
                  </span>
                </td>
                <td className="trade-journal-review">{trade.review || trade.thesis || '-'}</td>
                <td className="trade-actions">
                  <button onClick={() => edit(trade)}>Edit</button>
                  <button onClick={() => remove(trade.id)}>Del</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
