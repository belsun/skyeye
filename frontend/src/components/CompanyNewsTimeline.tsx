import { useEffect, useState } from 'react';
import { fetchCompanyProfile } from '../api';
import type { CompanyProfile } from '../types';

interface Props {
  symbol: string;
}

function shortDate(value?: string | null): string {
  if (!value) return '暂无日期';
  return value.slice(0, 10);
}

function sentimentLabel(value?: string | null): string {
  if (!value) return '中性';
  if (value.includes('positive')) return '利好';
  if (value.includes('negative')) return '利空';
  return '中性';
}

export default function CompanyNewsTimeline({ symbol }: Props) {
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    fetchCompanyProfile(symbol, false)
      .then(setProfile)
      .catch(() => setProfile(null))
      .finally(() => setLoading(false));
  }, [symbol]);

  const items = profile?.recent_news || [];

  return (
    <section className="company-news-timeline">
      <div className="company-news-head">
        <div>
          <span>公司新闻时间线</span>
          <h3>企业自身动态，贴着 K 线看</h3>
        </div>
        <em>{loading ? '更新中...' : `${items.length} 条`}</em>
      </div>

      {items.length > 0 ? (
        <div className="company-news-grid">
          {items.slice(0, 6).map((item) => (
            <a key={item.id} href={item.article_url || undefined} target="_blank" rel="noreferrer">
              <div className="company-news-meta">
                <span>{shortDate(item.published_utc)}</span>
                <strong className={`company-news-sentiment ${item.sentiment || 'neutral'}`}>
                  {sentimentLabel(item.sentiment)}
                </strong>
              </div>
              <h4>{item.title}</h4>
              {(item.chinese_summary || item.description) && (
                <p>{item.chinese_summary || item.description}</p>
              )}
              <small>{item.publisher || '公开新闻源'}</small>
            </a>
          ))}
        </div>
      ) : (
        <div className="company-news-empty">
          {loading ? '正在读取公司新闻...' : '暂未抓取到公司近期新闻。加入 Tracking 后会按需抓取，并定期清理旧缓存。'}
        </div>
      )}
    </section>
  );
}
