import { useState, useEffect } from 'react';
import { fetchTrending } from '../api';
import type { TrendingTopic } from '../types';

export default function TrendingTopics() {
  const [topics, setTopics] = useState<TrendingTopic[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchTrending()
      .then((data) => setTopics(data.topics))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading && topics.length === 0) return <div className="loading-placeholder">加载中...</div>;
  if (topics.length === 0) return null;

  const maxMentions = Math.max(...topics.map((t) => t.mentions));

  return (
    <div className="trending-topics">
      <div className="topic-cloud">
        {topics.map((topic, i) => {
          const size = 0.7 + (topic.mentions / maxMentions) * 0.6;
          const opacity = 0.5 + (topic.mentions / maxMentions) * 0.5;
          return (
            <span
              key={i}
              className="topic-tag"
              style={{ fontSize: `${size}rem`, opacity }}
            >
              {topic.keyword}
              <span className="topic-count">{topic.mentions}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
