import { useState, useEffect, memo } from 'react';
import { fetchNews, fetchGeopolitical } from '../api';
import type { NewsArticle, GeopoliticalData } from '../types';

const FILTERS: Array<{ key: string; label: string; sentiment?: string; category?: string }> = [
  { key: 'all', label: '全部 / All' },
  { key: 'positive', label: '利好 🟢', sentiment: 'positive' },
  { key: 'neutral', label: '中性 🟡', sentiment: 'neutral' },
  { key: 'negative', label: '利空 🔴', sentiment: 'negative' },
  { key: 'us', label: '美股 / US', category: 'us' },
  { key: 'hk', label: '港股 / HK', category: 'hk' },
  { key: 'hk_ipo', label: '港股打新', category: 'hk_ipo' },
  { key: 'macro', label: '宏观 / Macro', category: 'macro' },
  { key: 'central_bank', label: '央行政策', category: 'central_bank' },
  { key: 'geopolitics', label: '地缘风险', category: 'geopolitics' },
  { key: 'earnings', label: '财报 / Earnings', category: 'earnings' },
  { key: 'ai', label: 'AI 风口', category: 'ai' },
  { key: 'semiconductor', label: '半导体', category: 'semiconductor' },
  { key: 'supply_chain', label: '产业链', category: 'supply_chain' },
  { key: 'liquidity', label: '流动性', category: 'liquidity' },
  { key: 'crypto', label: '加密', category: 'crypto' },
];

const GEO_FILTER_ICONS: Record<string, string> = {
  trade: '⚔️',
  sanctions: '🚫',
  taiwan: '🌊',
  conflict: '💥',
  monetary: '🏦',
  economy: '📉',
  tech: '💡',
  danger: '🔴',
  trade_war: '⚔️',
  taiwan_strait: '🌊',
  geopolitical_conflict: '💥',
  central_bank: '🏦',
  economic_risk: '📉',
  tech_competition: '💡',
  military_risk: '🔴',
};

function parseDate(dateStr: string): number {
  if (!dateStr) return NaN;
  // Try native parsing first
  const t = new Date(dateStr).getTime();
  if (!isNaN(t) && t > 0) return t;
  // Try replacing 'T' separator if missing
  const cleaned = dateStr.replace(/\s+/, 'T');
  const t2 = new Date(cleaned).getTime();
  if (!isNaN(t2) && t2 > 0) return t2;
  // Try extracting just YYYY-MM-DD
  const m = dateStr.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (m) return new Date(`${m[1]}-${m[2]}-${m[3]}T00:00:00Z`).getTime();
  return NaN;
}

function formatPublishedTime(dateStr: string): string {
  const ts = parseDate(dateStr);
  if (isNaN(ts)) return '';
  const d = new Date(ts);
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = parseDate(dateStr);
  if (isNaN(then)) return '';
  const diff = now - then;
  if (diff < 0) return '刚刚';
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
  if (diff < 172800000) return '昨天';
  // Show actual date for older articles
  const d = new Date(then);
  const month = d.getMonth() + 1;
  const day = d.getDate();
  const year = d.getFullYear();
  const curYear = new Date(now).getFullYear();
  if (year === curYear) return `${month}月${day}日`;
  return `${year}/${month}/${day}`;
}

interface GeoCategory {
  key: string;
  name: string;
  score: number;
}

export default memo(function NewsFeed() {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [activeFilter, setActiveFilter] = useState('all');
  const [activeGeoCategory, setActiveGeoCategory] = useState<string | null>(null);
  const [geoCategories, setGeoCategories] = useState<GeoCategory[]>([]);
  const [loading, setLoading] = useState(false);

  // Fetch geopolitical categories on mount
  useEffect(() => {
    fetchGeopolitical()
      .then((data: GeopoliticalData) => {
        if (data.categories && data.categories.length > 0) {
          // Map categories to include key if not present
          const mapped = data.categories.map((cat: any, i: number) => ({
            key: cat.key || cat.name?.toLowerCase().replace(/\s+/g, '_') || `geo_${i}`,
            name: cat.name,
            score: cat.score,
          }));
          setGeoCategories(mapped);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const selected = FILTERS.find((item) => item.key === activeFilter);
    const sentiment = selected?.sentiment;
    const category = activeGeoCategory || selected?.category;

    fetchNews(sentiment, category)
      .then((data) => {
        setArticles(data.articles);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [activeFilter, activeGeoCategory]);

  const sentimentClass = (s: string) => {
    if (s === 'positive') return 'sentiment-positive';
    if (s === 'negative') return 'sentiment-negative';
    return 'sentiment-neutral';
  };

  const sentimentDot = (s: string) => {
    if (s === 'positive') return '🟢';
    if (s === 'negative') return '🔴';
    return '🟡';
  };

  const handleGeoCategoryClick = (key: string) => {
    setActiveGeoCategory(prev => prev === key ? null : key);
  };

  return (
    <div className="news-feed">
      <div className="news-source-strip">
        <span>Authority Sources</span>
        <strong>Bloomberg</strong>
        <strong>HKEX</strong>
        <strong>SEC</strong>
        <strong>Fed</strong>
        <strong>CNBC</strong>
        <strong>Yahoo Finance</strong>
      </div>
      <div className="news-feed-filters">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`news-filter-btn ${activeFilter === f.key ? 'active' : ''}`}
            onClick={() => {
              setActiveFilter(f.key);
              setActiveGeoCategory(null);
            }}
            title={f.category ? `按 ${f.category} 分类筛选` : undefined}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Geopolitical category tags */}
      {geoCategories.length > 0 && (
        <div className="news-geo-filters">
          {geoCategories.map((cat) => (
            <button
              key={cat.key}
              className={`news-geo-tag ${activeGeoCategory === cat.key ? 'active' : ''}`}
              onClick={() => handleGeoCategoryClick(cat.key)}
              title={`按 ${cat.name} 筛选新闻 (风险: ${cat.score.toFixed(1)})`}
            >
              <span className="news-geo-icon">{GEO_FILTER_ICONS[cat.key] || '🌐'}</span>
              <span className="news-geo-name">{cat.name}</span>
            </button>
          ))}
        </div>
      )}

      {loading && articles.length === 0 ? (
        <div className="loading-placeholder">加载中...</div>
      ) : (
        <div className="news-feed-list">
          {articles.map((article, i) => (
            <a
              key={article.id || i}
              href={article.url}
              target="_blank"
              rel="noreferrer"
              className={`news-feed-item ${sentimentClass(article.sentiment)}`}
            >
              <div className="news-feed-item-left">
                <span className="news-feed-dot">{sentimentDot(article.sentiment)}</span>
              </div>
              <div className="news-feed-item-body">
                <div className="news-feed-title">{article.title}</div>
                <div className="news-feed-meta">
                  <span className="news-feed-source">{article.source}</span>
                  <span className="news-feed-time" title={timeAgo(article.published)}>{formatPublishedTime(article.published)}</span>
                </div>
                {article.tags && article.tags.length > 0 && (
                  <div className="news-feed-tags">
                    {article.tags.slice(0, 5).map((tag, j) => (
                      <span key={`${tag.key || tag.value}-${j}`} className="news-feed-tag">{tag.value}</span>
                    ))}
                  </div>
                )}
              </div>
            </a>
          ))}
          {articles.length === 0 && !loading && (
            <div className="news-empty-state">暂无新闻</div>
          )}
        </div>
      )}
    </div>
  );
});
