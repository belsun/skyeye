const LEARNING_STAGES = [
  {
    title: '数据与标签 / Data',
    body: '先保证 K 线、新闻、情绪标签稳定，再谈模型胜率。没有干净样本，量化结果会像噪音。',
    metrics: ['OHLC ≥ 200', 'News labels ≥ 50', 'No stale data'],
  },
  {
    title: '回测与模拟 / Backtest',
    body: '用 paper portfolio 验证策略相对等权基准有没有超额收益，同时记录最大回撤。',
    metrics: ['Out-of-sample', 'Drawdown', 'Sharpe'],
  },
  {
    title: '小仓位验证 / Pilot',
    body: '当信号、风险、催化同向时，只用小风险预算验证流程，不把模型输出当成买卖指令。',
    metrics: ['0.25%-0.5% risk', 'ATR stop', 'Trade journal'],
  },
];

const CAPITAL_BLOCKS = [
  { label: 'HKD 1,000,000', text: '港股打新、科技股核心观察、现金缓冲' },
  { label: 'USD 40,000', text: '美股 AI/半导体主题、模拟组合与小仓位实验' },
  { label: 'Focus', text: '先建研究流程，再决定真实仓位' },
];

export default function QuantStarterPanel() {
  return (
    <div className="quant-starter">
      <div className="quant-starter-header">
        <div>
          <span className="quant-starter-title">
            <span className="zh-copy">量化入门舱</span>
            <span className="en-copy">Quant Starter</span>
          </span>
          <span className="quant-starter-status">Beginner Friendly</span>
        </div>
        <span className="quant-starter-note">Research Only</span>
      </div>

      <div className="quant-starter-capital">
        {CAPITAL_BLOCKS.map((item) => (
          <span key={item.label}>
            {item.label}
            <strong>{item.text}</strong>
          </span>
        ))}
      </div>

      <div className="quant-starter-grid">
        {LEARNING_STAGES.map((stage, index) => (
          <div key={stage.title} className="quant-starter-stage">
            <div className="quant-stage-index">{index + 1}</div>
            <strong>{stage.title}</strong>
            <p>{stage.body}</p>
            <div className="quant-stage-tags">
              {stage.metrics.map((metric) => <span key={metric}>{metric}</span>)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
