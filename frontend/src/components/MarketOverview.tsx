import { useState, useEffect, useCallback, memo } from 'react';
import { fetchMarketOverview } from '../api';
import type { MarketOverviewData, MarketItem } from '../types';

interface Props {
  filter?: string;
  onStockClick: (symbol: string) => void;
}

function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 60;
  const h = 20;
  const points = data.map((v, i) => {
    const px = (i / (data.length - 1)) * w;
    const py = h - ((v - min) / range) * h;
    return `${px},${py}`;
  }).join(' ');
  return (
    <svg width={w} height={h} className="sparkline">
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={points} />
    </svg>
  );
}

function MarketCard({ item, onClick }: { item: MarketItem; onClick: () => void }) {
  const isUp = item.change_pct >= 0;
  const color = isUp ? '#10b981' : '#ef4444';
  return (
    <div className="market-card" onClick={onClick}>
      <div className="market-card-header">
        <span className="market-card-icon">{item.icon || '📊'}</span>
        <span className="market-card-name">{item.name}</span>
      </div>
      <div className="market-card-body">
        <span className="market-card-price">{item.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        <span className="market-card-change" style={{ color }}>
          {isUp ? '+' : ''}{item.change_pct.toFixed(2)}%
        </span>
      </div>
      {item.sparkline && <MiniSparkline data={item.sparkline} color={color} />}
    </div>
  );
}

function MarketStatusBar({ status }: { status: Record<string, any> | undefined }) {
  if (!status) return null;
  const markets = [
    { key: 'us', label: '🇺🇸 美股' },
    { key: 'hk', label: '🇭🇰 港股' },
    { key: 'cn', label: '🇨🇳 A股' },
    { key: 'jp', label: '🇯🇵 日股' },
    { key: 'eu', label: '🇪🇺 欧股' },
  ];
  const entries = markets.filter(m => status[m.key]);
  if (entries.length === 0) return null;
  return (
    <div className="market-status-bar">
      {entries.map(m => {
        const s = status[m.key];
        const isOpen = s.status === 'open';
        const isClosed = s.status === 'closed';
        const dotColor = isOpen ? '#10b981' : isClosed ? '#ef4444' : '#f59e0b';
        return (
          <div key={m.key} className="market-status-item">
            <span className="market-status-dot" style={{ background: dotColor }} />
            <span className="market-status-label">{m.label}</span>
            {s.time && <span className="market-status-time">{s.time}</span>}
          </div>
        );
      })}
    </div>
  );
}

export default function MarketOverview({ filter, onStockClick }: Props) {
  const [data, setData] = useState<MarketOverviewData | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    fetchMarketOverview()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, [load]);

  if (loading && !data) return (
    <div className="market-overview">
      {['skeleton-1', 'skeleton-2'].map((key) => (
        <div key={key} className="market-section">
          <div className="skeleton-bar" style={{ width: 100, height: 12, marginBottom: 8 }} />
          <div className="market-grid">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="market-card skeleton-card">
                <div className="skeleton-bar" style={{ width: 60, height: 10, marginBottom: 6 }} />
                <div className="skeleton-bar" style={{ width: 80, height: 14 }} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
  if (!data) return null;

  const sections: { title: string; items: MarketItem[] }[] = [];

  if (!filter || filter === 'overview') {
    if (data.markets.us.indices.length) sections.push({ title: '🇺🇸 美股指数', items: data.markets.us.indices });
    if (data.markets.hk.indices.length) sections.push({ title: '🇭🇰 港股指数', items: data.markets.hk.indices });
    if (data.markets.cn.indices.length) sections.push({ title: '🇨🇳 A股指数', items: data.markets.cn.indices });
    if (data.markets.jp?.indices?.length) sections.push({ title: '🇯🇵 日经指数', items: data.markets.jp.indices });
    if (data.markets.eu?.indices?.length) sections.push({ title: '🇪🇺 欧洲指数', items: data.markets.eu.indices });
    if (data.crypto?.length) sections.push({ title: '₿ 加密货币', items: data.crypto });
    if (data.commodities?.length) sections.push({ title: '🥇 大宗商品', items: data.commodities });
  } else if (filter === 'us') {
    if (data.markets.us.indices.length) sections.push({ title: '美股指数', items: data.markets.us.indices });
    if (data.markets.us.stocks?.length) sections.push({ title: '热门美股', items: data.markets.us.stocks });
  } else if (filter === 'hk') {
    if (data.markets.hk.indices.length) sections.push({ title: '港股指数', items: data.markets.hk.indices });
    if (data.markets.hk.stocks?.length) sections.push({ title: '热门港股', items: data.markets.hk.stocks });
  } else if (filter === 'cn') {
    if (data.markets.cn.indices.length) sections.push({ title: 'A股指数', items: data.markets.cn.indices });
  } else if (filter === 'jp') {
    if (data.markets.jp?.indices?.length) sections.push({ title: '日经指数', items: data.markets.jp.indices });
    if (data.markets.jp?.stocks?.length) sections.push({ title: '热门日股', items: data.markets.jp.stocks });
  } else if (filter === 'eu') {
    if (data.markets.eu?.indices?.length) sections.push({ title: '欧洲指数', items: data.markets.eu.indices });
    if (data.markets.eu?.stocks?.length) sections.push({ title: '热门欧股', items: data.markets.eu.stocks });
  } else if (filter === 'crypto') {
    if (data.crypto?.length) sections.push({ title: '加密货币', items: data.crypto });
  } else if (filter === 'commodities') {
    if (data.commodities?.length) sections.push({ title: '大宗商品', items: data.commodities });
  } else if (filter === 'watchlist') {
    // Show all items in a combined view
    const allItems = [
      ...data.markets.us.indices.slice(0, 3),
      ...data.markets.hk.indices.slice(0, 2),
      ...(data.crypto?.slice(0, 3) || []),
    ];
    if (allItems.length) sections.push({ title: '自选关注', items: allItems });
  }

  return (
    <div className="market-overview">
      <MarketStatusBar status={data.status} />
      {sections.map((section) => (
        <div key={section.title} className="market-section">
          <div className="market-section-title">{section.title}</div>
          <div className="market-grid">
            {section.items.map((item) => (
              <MarketCard
                key={item.symbol}
                item={item}
                onClick={() => onStockClick(item.symbol)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
