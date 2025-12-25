import React, { useEffect, useState } from 'react';
import API_URL from '../config/api';
import { HotDataResponse } from '../types';

interface HotDataPanelProps {
  onSelectTopic: (topic: string) => void;
}

const HotDataPanel: React.FC<HotDataPanelProps> = ({ onSelectTopic }) => {
  const [data, setData] = useState<HotDataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeNewsSource, setActiveNewsSource] = useState<string>('weibo');
  const [selectedNewsItems, setSelectedNewsItems] = useState<Set<string>>(new Set());
  const [selectedPolymarketItems, setSelectedPolymarketItems] = useState<Set<string>>(new Set());

  // Source name mapping
  const sourceNames: { [key: string]: string } = {
    'weibo': '微博热搜',
    'zhihu': '知乎热榜',
    'baidu': '百度热搜',
    'toutiao': '今日头条',
    'douyin': '抖音热搜',
    'bilibili': 'B站热门',
    'thepaper': '澎湃新闻',
    '36kr': '36氪',
    'ithome': 'IT之家',
    'wallstreetcn': '华尔街见闻',
    'cls': '财联社',
    'caixin': '财新网',
    'yicai': '第一财经',
    'sina-finance': '新浪财经',
    'eastmoney': '东方财富',
    'jiemian': '界面新闻'
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      console.log('[HotDataPanel] Fetching from:', `${API_URL}/api/hot-data`);
      const response = await fetch(`${API_URL}/api/hot-data`);
      console.log('[HotDataPanel] Response status:', response.status);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      console.log('[HotDataPanel] Data received:', result);
      
      if (result.status === 'success') {
        setData(result);
        setError(null);
        // Set first available news source as default if not already set
        if (result.newsnow && Object.keys(result.newsnow).length > 0) {
          const sources = Object.keys(result.newsnow);
          if (!activeNewsSource || !sources.includes(activeNewsSource)) {
            setActiveNewsSource(sources[0]);
          }
        }
      } else {
        setError(result.message || 'Failed to fetch hot data');
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Error connecting to server';
      setError(errorMsg);
      console.error('[HotDataPanel] Error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <div className="hot-data-loading" style={{ minHeight: '200px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <i className="fas fa-spinner fa-spin" style={{ fontSize: '24px', marginBottom: '12px', color: 'var(--accent-color)' }}></i>
        <p>Loading trending topics and prediction markets...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="hot-data-error" style={{ minHeight: '200px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <i className="fas fa-exclamation-circle" style={{ fontSize: '24px', marginBottom: '12px', color: 'var(--negative-color)' }}></i>
        <p>{error}</p>
        <button onClick={fetchData} className="btn-primary" style={{ marginTop: '12px' }}>Retry</button>
      </div>
    );
  }

  // Ensure data structures exist to prevent white screen
  const newsnow = data?.newsnow || {};
  const polymarket = Array.isArray(data?.polymarket) ? data.polymarket : [];
  const sources = Object.keys(newsnow);
  
  // Safely get current news items
  const currentNewsItems = (() => {
    try {
      if (!activeNewsSource) return [];
      const items = newsnow[activeNewsSource];
      return Array.isArray(items) ? items : [];
    } catch (e) {
      console.error('[HotDataPanel] Error getting news items:', e);
      return [];
    }
  })();

  const handleNewsItemToggle = (title: string) => {
    setSelectedNewsItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(title)) {
        newSet.delete(title);
      } else {
        newSet.add(title);
      }
      return newSet;
    });
  };

  const handlePolymarketToggle = (id: string) => {
    setSelectedPolymarketItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  const handleAnalyzeSelected = () => {
    const selectedNews = Array.from(selectedNewsItems);
    const selectedPoly = Array.from(selectedPolymarketItems).map(id => 
      polymarket.find(e => e.id === id)?.question
    ).filter(Boolean);
    
    const allSelected = [...selectedNews, ...selectedPoly];
    if (allSelected.length === 0) {
      alert('Please select at least one item to analyze');
      return;
    }
    
    const prompt = `Analyze the following hot topics and their potential market impact:\n\n${allSelected.map((item, i) => `${i + 1}. ${item}`).join('\n')}`;
    onSelectTopic(prompt);
    
    // Clear selections after analysis
    setSelectedNewsItems(new Set());
    setSelectedPolymarketItems(new Set());
  };

  const totalSelected = selectedNewsItems.size + selectedPolymarketItems.size;

  return (
    <div className="hot-data-panel-v2">
      <div className="hot-data-grid">
        {/* Left Column: Social Media */}
        <div className="hot-data-column">
          <div className="column-header">
            <h4><i className="fas fa-hashtag"></i> Social Media Trends</h4>
            <select 
              className="source-dropdown"
              value={activeNewsSource}
              onChange={(e) => setActiveNewsSource(e.target.value)}
            >
              {sources.map(source => (
                <option key={source} value={source}>
                  {sourceNames[source] || source.charAt(0).toUpperCase() + source.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div className="column-content">
            <ul className="topic-list">
              {currentNewsItems && currentNewsItems.length > 0 ? (
                currentNewsItems.map((item, idx) => (
                  <li key={idx} className="topic-item">
                    <input 
                      type="checkbox" 
                      className="topic-checkbox"
                      checked={selectedNewsItems.has(item.title)}
                      onChange={(e) => {
                        e.stopPropagation();
                        handleNewsItemToggle(item.title);
                      }}
                    />
                    <span className="rank">{idx + 1}</span>
                    <a 
                      href={item.url} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="title"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {item.title}
                    </a>
                    {item.hot_value && <span className="hot-value">{item.hot_value}</span>}
                  </li>
                ))
              ) : (
                <div className="empty-state">No social trends found</div>
              )}
            </ul>
          </div>
        </div>

        {/* Right Column: Polymarket */}
        <div className="hot-data-column">
          <div className="column-header">
            <h4><i className="fas fa-chart-line"></i> Prediction Markets</h4>
            <span className="source-badge">Polymarket</span>
          </div>
          <div className="column-content">
            <ul className="event-list">
              {polymarket && polymarket.length > 0 ? (
                polymarket.map((event) => {
                  // Safety checks
                  if (!event || !event.id || !event.question) return null;
                  
                  return (
                    <li key={event.id} className="event-item">
                      <input 
                        type="checkbox" 
                        className="event-checkbox"
                        checked={selectedPolymarketItems.has(event.id)}
                        onChange={(e) => {
                          e.stopPropagation();
                          handlePolymarketToggle(event.id);
                        }}
                      />
                      <div className="event-content">
                        <div className="event-question">{event.question}</div>
                        <div className="event-outcomes">
                          {Array.isArray(event.outcomes) && event.outcomes.map((outcome, i) => (
                            <div key={i} className="outcome-pill">
                              <span className="outcome-name">{outcome}</span>
                              <span className="outcome-price">
                                {event.outcomePrices && event.outcomePrices[i] 
                                  ? (parseFloat(event.outcomePrices[i]) * 100).toFixed(1) 
                                  : '0'}%
                              </span>
                            </div>
                          ))}
                        </div>
                        <div className="event-meta">
                          <span>Vol: ${event.volume ? parseFloat(event.volume).toLocaleString() : '0'}</span>
                          <span>Updated: {event.updatedAt ? new Date(event.updatedAt).toLocaleDateString() : 'N/A'}</span>
                        </div>
                      </div>
                    </li>
                  );
                })
              ) : (
                <div className="empty-state">No prediction markets found</div>
              )}
            </ul>
          </div>
        </div>
      </div>
      <div className="hot-data-footer">
        <span className="last-updated">
          Auto-refreshes every 5m {totalSelected > 0 && `• ${totalSelected} selected`}
        </span>
        <div className="footer-actions">
          {totalSelected > 0 && (
            <button 
              className="analyze-btn" 
              onClick={handleAnalyzeSelected}
            >
              <i className="fas fa-chart-bar"></i> Analyze Selected ({totalSelected})
            </button>
          )}
          <button className="refresh-btn" onClick={fetchData} disabled={loading}>
            <i className={`fas fa-sync-alt ${loading ? 'fa-spin' : ''}`}></i> {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default HotDataPanel;
