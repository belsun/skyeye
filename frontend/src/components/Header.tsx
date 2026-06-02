import { useState, useEffect, useRef } from 'react';
import { fetchSearch } from '../api';
import type { SearchResult } from '../types';

interface Props {
  viewMode: 'overview' | 'deep';
  selectedSymbol: string;
  onBack: () => void;
  onSearchSelect: (symbol: string) => void;
  themeMode: 'midnight' | 'hk' | 'terminal';
  languageMode: 'zh' | 'en' | 'both';
  learningMode: 'learning' | 'pro';
  onThemeChange: (mode: 'midnight' | 'hk' | 'terminal') => void;
  onLanguageChange: (mode: 'zh' | 'en' | 'both') => void;
  onLearningModeChange: (mode: 'learning' | 'pro') => void;
}

function getMarketBadge(symbol: string): { label: string; color: string } | null {
  if (symbol.endsWith('.HK')) return { label: 'HK', color: '#ef5350' };
  if (symbol.endsWith('.SS')) return { label: 'CN-SH', color: '#ff9800' };
  if (symbol.endsWith('.SZ')) return { label: 'CN-SZ', color: '#ff9800' };
  if (symbol.endsWith('.T')) return { label: 'JP', color: '#e91e63' };
  if (symbol.endsWith('.L')) return { label: 'UK', color: '#9c27b0' };
  if (symbol.startsWith('^')) return { label: 'IDX', color: '#667eea' };
  if (/-USD$/.test(symbol)) return { label: 'CRYPTO', color: '#f59e0b' };
  if (/^(GC|CL|SI|HG|NG|PA|PL)=F$/.test(symbol)) return { label: 'CMDTY', color: '#795548' };
  return null;
}

export default function Header({
  viewMode,
  selectedSymbol,
  onBack,
  onSearchSelect,
  themeMode,
  languageMode,
  learningMode,
  onThemeChange,
  onLanguageChange,
  onLearningModeChange,
}: Props) {
  const [clock, setClock] = useState('');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Live clock
  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setClock(now.toLocaleTimeString('en-US', { hour12: false }));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  // Debounced search
  useEffect(() => {
    if (!query.trim() || query.trim().length < 2) { setResults([]); return; }
    const id = setTimeout(() => {
      setLoading(true);
      // Support multi-market: detect numeric codes for HK, CN, JP
      let searchQuery = query.trim();
      const numMatch = searchQuery.match(/^(\d{4,6})$/);
      if (numMatch) {
        const code = numMatch[1];
        if (code.length === 4) {
          // Could be HK stock (e.g., 0700)
          searchQuery = `${code}.HK`;
        } else if (code.length === 6) {
          // Could be A-share (e.g., 600519)
          if (code.startsWith('6')) {
            searchQuery = `${code}.SS`;
          } else if (code.startsWith('0') || code.startsWith('3')) {
            searchQuery = `${code}.SZ`;
          }
        }
      }

      fetchSearch(searchQuery)
        .then((data) => setResults(data.results))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(id);
  }, [query]);

  // Click outside to close
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <header className="app-header">
      <div className="header-left">
        {viewMode === 'deep' ? (
          <button className="back-btn" onClick={onBack}>
            <span className="back-arrow">←</span>
            <span>返回</span>
          </button>
        ) : null}
        <div className="logo" onClick={viewMode === 'deep' ? onBack : undefined}>
          <span className="logo-icon">👁️</span>
          <span className="logo-text">天眼 SkyEye</span>
        </div>
      </div>

      <div className="header-center">
        <div className="search-wrap" ref={wrapRef}>
          <input
            ref={inputRef}
            className="search-input"
            type="text"
            placeholder="搜索股票... MiniMax, 00100.HK, 0700.HK, AAPL"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setShowDropdown(true); }}
            onFocus={() => query.trim() && setShowDropdown(true)}
          />
          {showDropdown && (results.length > 0 || loading) && (
            <div className="search-dropdown">
              {loading && <div className="search-loading">搜索中...</div>}
              {results.map((r) => {
                const badge = getMarketBadge(r.symbol);
                return (
                  <div
                    key={r.symbol}
                    className="search-result-item"
                    onClick={() => {
                      onSearchSelect(r.symbol);
                      setQuery('');
                      setShowDropdown(false);
                    }}
                  >
                    <span className="search-symbol">{r.symbol}</span>
                    <span className="search-name">
                      {r.name}
                      {r.sector && <em>{r.sector}</em>}
                    </span>
                    {badge && (
                      <span
                        className="search-type"
                        style={{ background: `${badge.color}22`, color: badge.color, borderColor: `${badge.color}44` }}
                      >
                        {badge.label}
                      </span>
                    )}
                    {r.type && !badge && <span className="search-type">{r.type}</span>}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="header-right">
        <div className="header-controls">
          <select
            className="theme-select"
            value={themeMode}
            title="配色方案 / Theme"
            onChange={(e) => onThemeChange(e.target.value as 'midnight' | 'hk' | 'terminal')}
          >
            <option value="midnight">Midnight</option>
            <option value="hk">HK Tech</option>
            <option value="terminal">Terminal</option>
          </select>
          <div className="lang-toggle" title="语言 / Language">
            {(['zh', 'en', 'both'] as const).map((mode) => (
              <button
                key={mode}
                className={languageMode === mode ? 'active' : ''}
                onClick={() => onLanguageChange(mode)}
              >
                {mode === 'zh' ? '中' : mode === 'en' ? 'EN' : '双'}
              </button>
            ))}
          </div>
          <button
            className={`learning-toggle ${learningMode}`}
            onClick={() => onLearningModeChange(learningMode === 'learning' ? 'pro' : 'learning')}
            title="学习模式 / Pro mode"
          >
            {learningMode === 'learning' ? '学习' : 'Pro'}
          </button>
        </div>
        {viewMode === 'deep' && selectedSymbol && (
          <span className="header-symbol-badge">{selectedSymbol}</span>
        )}
        <div className="live-indicator">
          <span className="live-dot" />
          <span className="live-text">LIVE</span>
        </div>
        <span className="header-clock">{clock}</span>
        <a className="github-link" href="https://github.com/belsun" target="_blank" rel="noreferrer">
          GitHub
        </a>
      </div>
    </header>
  );
}
