import { useEffect, useState } from 'react';
import { fetchCompanyProfile } from '../api';
import type { CompanyProfile } from '../types';

interface Props {
  symbol: string;
}

function shortDate(value?: string | null): string {
  if (!value) return '暂无';
  return value.slice(0, 10);
}

function sentimentText(value?: string | null): string {
  if (!value) return '中性';
  if (value.includes('positive')) return '偏利好';
  if (value.includes('negative')) return '偏利空';
  return '中性';
}

export default function CompanyProfilePanel({ symbol }: Props) {
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function load(refresh = false) {
    if (!symbol) return;
    setLoading(true);
    setError('');
    fetchCompanyProfile(symbol, refresh)
      .then(setProfile)
      .catch((err) => setError(err?.response?.data?.detail || err.message || '公司资料加载失败'))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    setProfile(null);
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol]);

  if (error) {
    return (
      <div className="company-profile-panel company-profile-empty">
        <div className="company-profile-title">公司档案</div>
        <span>{error}</span>
        <button onClick={() => load(true)}>重试</button>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="company-profile-panel company-profile-empty">
        <div className="company-profile-title">公司档案</div>
        <span>{loading ? '正在读取公司资料...' : '暂无公司资料'}</span>
      </div>
    );
  }

  const links = Object.entries(profile.links || {}).filter(([, url]) => !!url);

  return (
    <section className="company-profile-panel">
      <div className="company-profile-head">
        <div>
          <span className="company-profile-kicker">公司档案 / Company Profile</span>
          <h2>{profile.name_zh || profile.name || profile.symbol}</h2>
          <p>{profile.symbol} · {profile.market || '市场未知'} · {profile.sector || '板块待确认'}</p>
        </div>
        <button onClick={() => load(true)} disabled={loading}>
          {loading ? '刷新中...' : '刷新资料'}
        </button>
      </div>

      <div className="company-profile-grid">
        <div>
          <span>主营业务</span>
          <strong>{profile.industry || profile.sector || '待确认'}</strong>
        </div>
        <div>
          <span>国家/地区</span>
          <strong>{profile.country || profile.market || '待确认'}</strong>
        </div>
        <div>
          <span>交易货币</span>
          <strong>{profile.currency || '待确认'}</strong>
        </div>
        <div>
          <span>资料来源</span>
          <strong>{profile.source || '本地/公开源'}</strong>
        </div>
      </div>

      <p className="company-profile-summary">{profile.summary_zh || profile.summary || '暂未获取到简介。建议先查看官网、投资者关系和最近公告。'}</p>

      {links.length > 0 && (
        <div className="company-profile-links">
          {links.map(([label, url]) => (
            <a key={label} href={url} target="_blank" rel="noreferrer">{label}</a>
          ))}
        </div>
      )}

      <div className="company-profile-cache">
        <span>新闻缓存：最近抓取 {shortDate(profile.data_status?.last_news_fetch)}</span>
        <span>K线缓存：最近抓取 {shortDate(profile.data_status?.last_ohlc_fetch)}</span>
        <span>{profile.data_status?.cache_policy}</span>
      </div>

      <div className="company-profile-news">
        <div className="company-profile-subtitle">最近相关新闻</div>
        {profile.recent_news.length > 0 ? profile.recent_news.slice(0, 4).map((item) => (
          <a key={item.id} href={item.article_url || undefined} target="_blank" rel="noreferrer">
            <span>{item.publisher || '新闻源'} · {shortDate(item.published_utc)} · {sentimentText(item.sentiment)}</span>
            <strong>{item.title}</strong>
            {(item.chinese_summary || item.description) && <em>{item.chinese_summary || item.description}</em>}
          </a>
        )) : (
          <div className="company-profile-no-news">
            本地还没有这家公司的新闻索引。加入 Tracking 后会后台抓取；后续我会继续做“按需即时搜索 + 定期清理”。
          </div>
        )}
      </div>
    </section>
  );
}
