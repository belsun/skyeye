import { useState, useEffect } from 'react';
import axios from 'axios';

interface Props {
  symbol: string;
}

interface StorySection {
  title: string;
  content: string;
  icon: string;
  type: 'summary' | 'events' | 'bullish' | 'bearish' | 'recommendation' | 'default';
}

function parseStoryToSections(story: string): StorySection[] {
  if (!story) return [];
  const sections: StorySection[] = [];

  // Try to split by <h3> tags first (HTML response)
  const h3Parts = story.split(/<h3[^>]*>(.*?)<\/h3>/gi);
  if (h3Parts.length > 2) {
    for (let i = 1; i < h3Parts.length; i += 2) {
      const title = h3Parts[i].replace(/<[^>]*>/g, '').trim();
      const rawContent = (h3Parts[i + 1] || '').replace(/<[^>]*>/g, '').trim();
      if (title && rawContent) {
        const section = classifySection(title, rawContent);
        sections.push(section);
      }
    }
    if (sections.length > 0) return sections;
  }

  // Try to split by markdown-style headers (### or **)
  const mdParts = story.split(/\n(?=###\s|##\s|\*\*[A-Z])/);
  if (mdParts.length > 2) {
    for (const part of mdParts) {
      const lines = part.trim().split('\n');
      const firstLine = lines[0].replace(/^#+\s*/, '').replace(/\*\*/g, '').trim();
      const content = lines.slice(1).join('\n').trim();
      if (firstLine && content) {
        sections.push(classifySection(firstLine, content));
      }
    }
    if (sections.length > 0) return sections;
  }

  // Fallback: try to split by numbered sections or bold headers
  const numberedParts = story.split(/\n(?=\d+[\.\)]\s|[一二三四五六七八九十]+[、.]\s)/);
  if (numberedParts.length > 2) {
    for (const part of numberedParts) {
      const match = part.match(/^(\d+[\.\)]\s|[一二三四五六七八九十]+[、.]\s)?(.*)/);
      const title = match ? match[2].split('\n')[0].replace(/\*\*/g, '').trim() : '';
      const content = match ? part.replace(match[0], '').trim() : part.trim();
      if (title && content.length > 10) {
        sections.push(classifySection(title, content.slice(0, 500)));
      }
    }
    if (sections.length > 0) return sections;
  }

  // Last resort: treat as single block
  sections.push({
    title: '分析报告',
    content: story.replace(/<[^>]*>/g, '').trim().slice(0, 1000),
    icon: '📊',
    type: 'summary',
  });
  return sections;
}

function classifySection(title: string, content: string): StorySection {
  const t = title.toLowerCase();
  const titleZh = title;

  // Detect section type by keywords
  if (/summary|总结|概要|overview|概述/.test(t)) {
    return { title: titleZh, content: content.slice(0, 500), icon: '📊', type: 'summary' };
  }
  if (/event|事件|news|新闻|key|关键/.test(t)) {
    return { title: titleZh, content: content.slice(0, 500), icon: '📰', type: 'events' };
  }
  if (/bull|利多|看多|上涨|positive|growth|upside|机会/.test(t)) {
    return { title: titleZh, content: content.slice(0, 500), icon: '🟢', type: 'bullish' };
  }
  if (/bear|利空|看空|下跌|negative|risk|downside|风险/.test(t)) {
    return { title: titleZh, content: content.slice(0, 500), icon: '🔴', type: 'bearish' };
  }
  if (/recommend|建议|策略|conclusion|结论|outlook|展望/.test(t)) {
    return { title: titleZh, content: content.slice(0, 500), icon: '💡', type: 'recommendation' };
  }

  // Detect by emoji in title
  const emojiMatch = titleZh.match(/^([\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}])/u);
  const icon = emojiMatch ? emojiMatch[1] : '📌';

  return { title: titleZh, content: content.slice(0, 500), icon, type: 'default' };
}

export default function StoryPanel({ symbol }: Props) {
  const [story, setStory] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [visible, setVisible] = useState(true);

  // Clear story when symbol changes
  useEffect(() => {
    setStory('');
    setError('');
    setVisible(true);
  }, [symbol]);

  async function generateStory() {
    setLoading(true);
    setError('');
    try {
      const res = await axios.post('/api/analysis/story', { symbol });
      setStory(res.data.story);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to generate story');
    } finally {
      setLoading(false);
    }
  }

  if (!visible) return null;

  const sections = parseStoryToSections(story);

  return (
    <div className="story-panel">
      <div className="story-panel-header">
        <h2>📊 AI 趋势分析</h2>
        <button className="story-close-btn" onClick={() => setVisible(false)} title="关闭">
          ✕
        </button>
      </div>

      {!story && !loading && (
        <button className="generate-story-btn" onClick={generateStory} disabled={!symbol}>
          生成分析报告
        </button>
      )}

      {loading && (
        <div className="story-loading">
          <div className="story-spinner" />
          <span>正在分析 {symbol} 的市场趋势...</span>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {sections.length > 0 && (
        <div className="story-ppt">
          {sections.map((section, i) => (
            <div key={i} className={`story-slide story-slide-${section.type}`}>
              <div className="story-slide-header">
                <span className="story-slide-icon">{section.icon}</span>
                <span className="story-slide-title">{section.title}</span>
              </div>
              <div className="story-slide-content">
                {section.content}
              </div>
            </div>
          ))}
        </div>
      )}

      {story && sections.length === 0 && (
        <div className="story-content" dangerouslySetInnerHTML={{ __html: story }} />
      )}
    </div>
  );
}
