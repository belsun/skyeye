import { useState, useRef, useEffect } from 'react';
import { fetchSearch } from '../api';
import type { SearchResult } from '../types';

interface Props {
  activeTickers: string[];
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
  onAdd: (symbol: string) => void | Promise<void>;
}

function normalizeSymbolInput(value: string): string {
  const raw = value.trim().toUpperCase().replace(/\s+/g, '');
  if (!raw) return '';
  if (raw.endsWith('.HK')) {
    const code = raw.slice(0, -3);
    if (/^\d{1,5}$/.test(code)) return `${String(Number(code)).padStart(4, '0')}.HK`;
  }
  if (/^\d{1,5}$/.test(raw)) return `${String(Number(raw)).padStart(4, '0')}.HK`;
  if (/^\d{6}$/.test(raw)) return raw.startsWith('6') ? `${raw}.SS` : `${raw}.SZ`;
  return raw;
}

export default function StockSelector({ activeTickers, selectedSymbol, onSelect, onAdd }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const normalized = normalizeSymbolInput(query);
    if (!normalized) { setResults([]); return; }
    const id = setTimeout(() => {
      fetchSearch(normalized)
        .then((data) => setResults(data.results))
        .catch(() => setResults([]));
    }, 300);
    return () => clearTimeout(id);
  }, [query]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setShowSearch(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const normalizedQuery = normalizeSymbolInput(query);
  const alreadyTracking = !!normalizedQuery && activeTickers.includes(normalizedQuery);
  const canAddManual = normalizedQuery && !alreadyTracking;

  async function addSymbol(symbol: string) {
    const normalized = normalizeSymbolInput(symbol);
    if (!normalized) return;
    setAdding(true);
    setError('');
    try {
      await onAdd(normalized);
      onSelect(normalized);
      setQuery('');
      setResults([]);
      setShowSearch(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || '添加失败');
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="stock-selector">
      <div className="stock-tabs">
        {activeTickers.map((sym) => (
          <button
          key={sym}
          className={`stock-pill ${selectedSymbol === sym ? 'active' : ''}`}
          onClick={() => onSelect(sym)}
          >
            {sym}
          </button>
        ))}
      </div>

      <div className="stock-search-wrap" ref={wrapRef}>
        <button className="stock-add-btn" onClick={() => setShowSearch(!showSearch)}>
          + 添加
        </button>
        {showSearch && (
          <div className="stock-search-dropdown">
            <input
              className="stock-search-input"
              type="text"
              placeholder="输入股票代码，如 00100.HK / MiniMax / AAPL"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && normalizedQuery) {
                  e.preventDefault();
                  addSymbol(results[0]?.symbol || normalizedQuery);
                }
              }}
              autoFocus
            />
            {canAddManual && (
              <button
                className="stock-search-manual"
                disabled={adding}
                onClick={() => addSymbol(normalizedQuery)}
              >
                {adding ? '添加中...' : `加入 Tracking：${normalizedQuery}`}
              </button>
            )}
            {query.trim() && normalizedQuery.endsWith('.HK') && (
              <div className="stock-search-hint">
                港交所五位代码会映射到行情源四位代码，例如 00100.HK → 0100.HK。
              </div>
            )}
            {alreadyTracking && (
              <div className="stock-search-hint">已在 Tracking：{normalizedQuery}</div>
            )}
            {error && <div className="stock-search-error">{error}</div>}
            {results.length > 0 && (
              <div className="stock-search-results">
                {results.map((r) => (
                  <div
                    key={r.symbol}
                    className="stock-search-item"
                    onClick={() => addSymbol(r.symbol)}
                  >
                    <span className="stock-search-sym">{r.symbol}</span>
                    <span className="stock-search-name">
                      {r.name}
                      {r.sector && <em>{r.sector}</em>}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
