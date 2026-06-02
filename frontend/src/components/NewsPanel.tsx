import { useState, useEffect, useRef } from 'react';
import { fetchStockNews } from '../api';
import type { StockNewsItem } from '../types';

interface Props {
  symbol: string;
  hoveredDate: string | null;
  highlightedNewsId?: string | null;
  isLocked?: boolean;
  onUnlock?: () => void;
  highlightedCategoryIds?: string[];
}

function sortBySentiment(items: StockNewsItem[]): StockNewsItem[] {
  const order: Record<string, number> = { positive: 0, negative: 1, neutral: 2 };
  return [...items].sort((a, b) => {
    const sa = order[a.sentiment || 'neutral'] ?? 2;
    const sb = order[b.sentiment || 'neutral'] ?? 2;
    return sa - sb;
  });
}

function pct(v: number | null) {
  if (v === null || v === undefined) return '-';
  const pctVal = v * 100;
  const color = pctVal > 0 ? '#10b981' : pctVal < 0 ? '#ef4444' : '#5a6577';
  return <span style={{ color, fontWeight: 600 }}>{pctVal > 0 ? '+' : ''}{pctVal.toFixed(2)}%</span>;
}

export default function NewsPanel({ symbol, hoveredDate, highlightedNewsId, isLocked, onUnlock, highlightedCategoryIds }: Props) {
  const [news, setNews] = useState<StockNewsItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [displayDate, setDisplayDate] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const cacheRef = useRef<Map<string, StockNewsItem[]>>(new Map());
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!symbol || !hoveredDate) return;
    if (isLocked && displayDate === hoveredDate) return;

    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(() => {
      const cacheKey = `${symbol}_${hoveredDate}`;
      const cached = cacheRef.current.get(cacheKey);
      if (cached) {
        setNews(sortBySentiment(cached));
        setDisplayDate(hoveredDate);
        return;
      }

      setLoading(true);
      fetchStockNews(symbol, hoveredDate)
        .then((data) => {
          cacheRef.current.set(cacheKey, data);
          setNews(sortBySentiment(data));
          setDisplayDate(hoveredDate);
        })
        .catch(() => {})
        .finally(() => setLoading(false));
    }, 120);
  }, [symbol, hoveredDate]);

  useEffect(() => {
    cacheRef.current.clear();
    setNews([]);
    setDisplayDate(null);
  }, [symbol]);

  useEffect(() => {
    if (!highlightedNewsId || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-news-id="${highlightedNewsId}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [highlightedNewsId, news]);

  const categorySet = highlightedCategoryIds && highlightedCategoryIds.length > 0
    ? new Set(highlightedCategoryIds) : null;
  const hasAnyMatch = categorySet != null && news.some((item) => categorySet.has(item.news_id));
  const effectiveCategorySet = (categorySet != null && !hasAnyMatch) ? null : categorySet;

  if (!displayDate) {
    return (
      <div className="news-panel">
        <div className="news-panel-header"><h2>📰 新闻</h2></div>
        <div className="news-empty">点击图表中的日期查看新闻</div>
      </div>
    );
  }

  return (
    <div className="news-panel">
      <div className="news-panel-header">
        <h2>📰 新闻</h2>
        <span className="news-date-badge">{displayDate}</span>
        <span className="news-count">{news.length} 篇</span>
        {isLocked && (
          <button className="lock-badge" onClick={onUnlock} title="点击解锁">
            🔒 已锁定
          </button>
        )}
      </div>

      {loading && news.length === 0 ? (
        <div className="news-empty">加载中...</div>
      ) : news.length === 0 ? (
        <div className="news-empty">该日期无新闻</div>
      ) : (
        <div className="news-list" ref={listRef}>
          {news.map((item) => {
            const isDimmed = effectiveCategorySet != null && !effectiveCategorySet.has(item.news_id);
            return (
              <div
                key={item.news_id}
                data-news-id={item.news_id}
                className={`news-card ${item.sentiment === 'positive' ? 'card-positive' : item.sentiment === 'negative' ? 'card-negative' : 'card-neutral'}${highlightedNewsId === item.news_id ? ' card-highlighted' : ''}${isDimmed ? ' card-dimmed' : ''}`}
                style={{ cursor: item.article_url ? 'pointer' : undefined }}
                onClick={() => { if (item.article_url) window.open(item.article_url, '_blank', 'noreferrer'); }}
              >
                <div className="news-card-top">
                  <span className={`sentiment-dot ${item.sentiment || 'neutral'}`} />
                  <a href={item.article_url} target="_blank" rel="noreferrer" className="news-title">
                    {item.title}
                  </a>
                </div>

                {item.image_url && (
                  <div className="news-image-wrap">
                    <img src={item.image_url} alt="" className="news-image" loading="lazy"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                  </div>
                )}

                <div className="news-impact-box">
                  <div>
                    <span className={`news-impact-label ${item.sentiment || 'neutral'}`}>
                      {item.impact_label || '待观察'}
                    </span>
                    {item.category_tags?.slice(0, 3).map((tag) => (
                      <span key={`${item.news_id}-${tag.key}`} className="news-category-chip">{tag.label}</span>
                    ))}
                  </div>
                  <p>{item.impact_reason || '这条新闻还缺少足够标注，先观察价格和成交量反应。'}</p>
                  {item.next_watch && <em>下一步看：{item.next_watch}</em>}
                </div>

                {item.key_discussion && (
                  <p className="news-summary">{item.key_discussion}</p>
                )}

                {(item.reason_growth || item.reason_decrease) && (
                  <div className="news-reasons">
                    {item.reason_growth && (
                      <div className="reason up"><span className="reason-icon">+</span> {item.reason_growth}</div>
                    )}
                    {item.reason_decrease && (
                      <div className="reason down"><span className="reason-icon">-</span> {item.reason_decrease}</div>
                    )}
                  </div>
                )}

                <div className="news-card-footer">
                  <span className="news-publisher">{item.publisher}</span>
                  <div className="returns-chips">
                    <span className="ret-chip">T+1 {pct(item.ret_t1)}</span>
                    <span className="ret-chip">T+5 {pct(item.ret_t5)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
