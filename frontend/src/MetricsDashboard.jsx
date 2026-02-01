import React, { useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts';
import { TrendingUp, Clock, AlertCircle, Calendar, Trash2, RefreshCw, Filter } from 'lucide-react';
import axios from 'axios';

const API_URL = "http://127.0.0.1:8000";

export default function MetricsDashboard({ data, darkMode, onRefresh }) {
  const [dateRange, setDateRange] = useState({ start: '', end: '' });
  const [loading, setLoading] = useState(false);

  const handleDateFilter = (days) => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - days);
    
    const fmt = (d) => d.toISOString().split('T')[0];
    const newRange = { start: fmt(start), end: fmt(end) };
    setDateRange(newRange);
    onRefresh(newRange);
  };

  const applyCustomDate = () => {
    onRefresh(dateRange);
  };

  const handleResetMetrics = async () => {
    if (!confirm("This will clear all analytics data. Continue?")) return;
    setLoading(true);
    try {
      await axios.delete(`${API_URL}/analytics/reset`);
      onRefresh(dateRange);
    } finally {
      setLoading(false);
    }
  };

  const handleResetAll = async () => {
    if (!confirm("This will delete all traces and metrics. This cannot be undone. Continue?")) return;
    setLoading(true);
    try {
      await axios.delete(`${API_URL}/traces/reset`);
      onRefresh(dateRange);
    } finally {
      setLoading(false);
    }
  };

  if (!data) {
    return (
      <div className={`p-10 ${darkMode ? 'text-white/40' : 'text-gray-400'}`}>
        Initializing Analytics...
      </div>
    );
  }

  const COLORS = {
    grid: darkMode ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.06)",
    text: darkMode ? "rgba(255,255,255,0.5)" : "rgba(0,0,0,0.5)",
    chartLine: darkMode ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.6)",
    chartFill: darkMode ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.04)",
  };

  return (
    <div className="p-8 h-full overflow-y-auto">
      
      {/* CONTROL BAR */}
      <div className={`mb-8 p-4 rounded-xl flex flex-wrap gap-4 items-center justify-between border ${
        darkMode 
          ? 'bg-white/3 border-white/6' 
          : 'bg-black/2 border-black/6'
      }`}>
        
        {/* Date Filters */}
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${
            darkMode ? 'bg-white/5' : 'bg-black/4'
          }`}>
            <Calendar size={14} className={darkMode ? 'text-white/40' : 'text-gray-400'}/>
            <input 
              type="date" 
              value={dateRange.start}
              onChange={(e) => setDateRange({...dateRange, start: e.target.value})}
              className={`bg-transparent border-none text-xs outline-none w-24 ${
                darkMode ? 'text-white/80' : 'text-gray-700'
              }`}
            />
            <span className={darkMode ? 'text-white/20' : 'text-gray-300'}>→</span>
            <input 
              type="date" 
              value={dateRange.end}
              onChange={(e) => setDateRange({...dateRange, end: e.target.value})}
              className={`bg-transparent border-none text-xs outline-none w-24 ${
                darkMode ? 'text-white/80' : 'text-gray-700'
              }`}
            />
            <button 
              onClick={applyCustomDate} 
              className={`ml-2 p-1 rounded transition-colors ${
                darkMode 
                  ? 'hover:bg-white/10 text-white/50 hover:text-white/80' 
                  : 'hover:bg-black/5 text-gray-400 hover:text-gray-600'
              }`}
            >
              <Filter size={14}/>
            </button>
          </div>

          <div className="flex gap-1">
            <PresetButton label="24h" onClick={() => handleDateFilter(1)} darkMode={darkMode} />
            <PresetButton label="7d" onClick={() => handleDateFilter(7)} darkMode={darkMode} />
            <PresetButton label="30d" onClick={() => handleDateFilter(30)} darkMode={darkMode} />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button 
            onClick={handleResetMetrics}
            disabled={loading}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
              darkMode 
                ? 'text-amber-400/80 hover:bg-amber-500/10 hover:text-amber-400' 
                : 'text-amber-600 hover:bg-amber-50'
            } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> 
            Reset Stats
          </button>
          <button 
            onClick={handleResetAll}
            disabled={loading}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
              darkMode 
                ? 'text-red-400/80 hover:bg-red-500/10 hover:text-red-400' 
                : 'text-red-600 hover:bg-red-50'
            } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <Trash2 size={13} /> 
            Clear All
          </button>
        </div>
      </div>

      {/* METRICS GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 max-w-6xl mx-auto">
        
        {/* KPI CARD 1: ERROR RATE */}
        <div className={`p-6 rounded-xl border relative overflow-hidden ${
          darkMode 
            ? 'bg-white/3 border-white/6' 
            : 'bg-white border-gray-200 shadow-sm'
        }`}>
          <div className={`absolute top-4 right-4 ${
            darkMode ? 'text-white/5' : 'text-gray-100'
          }`}>
            <AlertCircle size={56} strokeWidth={1} />
          </div>
          <h3 className={`text-xs font-medium uppercase tracking-wide mb-2 ${
            darkMode ? 'text-white/40' : 'text-gray-500'
          }`}>
            Error Rate
          </h3>
          <div className={`text-4xl font-light tracking-tight ${
            data.error_rate > 0 
              ? 'text-red-400' 
              : darkMode ? 'text-emerald-400' : 'text-emerald-600'
          }`}>
            {data.error_rate}
            <span className={`text-lg ml-0.5 ${
              darkMode ? 'text-white/30' : 'text-gray-400'
            }`}>%</span>
          </div>
        </div>

        {/* KPI CARD 2: LATENCY */}
        <div className={`p-6 rounded-xl border relative overflow-hidden ${
          darkMode 
            ? 'bg-white/3 border-white/6' 
            : 'bg-white border-gray-200 shadow-sm'
        }`}>
          <div className={`absolute top-4 right-4 ${
            darkMode ? 'text-white/5' : 'text-gray-100'
          }`}>
            <Clock size={56} strokeWidth={1} />
          </div>
          <h3 className={`text-xs font-medium uppercase tracking-wide mb-2 ${
            darkMode ? 'text-white/40' : 'text-gray-500'
          }`}>
            Avg Latency (LLM)
          </h3>
          <div className={`text-4xl font-light tracking-tight ${
            darkMode ? 'text-white/90' : 'text-gray-800'
          }`}>
            {data.latency_by_type.find(x => x.type === 'llm')?.avg || 0}
            <span className={`text-lg ml-0.5 ${
              darkMode ? 'text-white/30' : 'text-gray-400'
            }`}>s</span>
          </div>
        </div>

        {/* PERFORMANCE TABLE */}
        <div className={`p-6 rounded-xl border col-span-1 md:col-span-2 ${
          darkMode 
            ? 'bg-white/3 border-white/6' 
            : 'bg-white border-gray-200 shadow-sm'
        }`}>
          <div className={`flex items-center gap-2 mb-5 ${
            darkMode ? 'text-white/70' : 'text-gray-700'
          }`}>
            <TrendingUp size={15} />
            <h3 className="text-sm font-medium">Component Performance</h3>
          </div>
          
          <div className={`overflow-hidden rounded-lg border ${
            darkMode ? 'border-white/6' : 'border-gray-200'
          }`}>
            <table className="w-full text-sm">
              <thead className={darkMode ? 'bg-white/3' : 'bg-gray-50'}>
                <tr className={`text-xs font-medium uppercase tracking-wide ${
                  darkMode ? 'text-white/40' : 'text-gray-500'
                }`}>
                  <th className="px-5 py-3 text-left">Component</th>
                  <th className="px-5 py-3 text-left">P95 Latency</th>
                  <th className="px-5 py-3 text-left">Avg Latency</th>
                </tr>
              </thead>
              <tbody className={`divide-y ${
                darkMode ? 'divide-white/5' : 'divide-gray-100'
              }`}>
                {data.latency_by_type.map((row) => (
                  <tr 
                    key={row.type} 
                    className={`transition-colors ${
                      darkMode ? 'hover:bg-white/3' : 'hover:bg-gray-50'
                    }`}
                  >
                    <td className={`px-5 py-3.5 font-mono text-sm ${
                      darkMode ? 'text-white/80' : 'text-gray-800'
                    }`}>
                      {row.type}
                    </td>
                    <td className={`px-5 py-3.5 font-mono ${
                      darkMode ? 'text-white/60' : 'text-gray-600'
                    }`}>
                      {row.p95}s
                    </td>
                    <td className={`px-5 py-3.5 ${
                      darkMode ? 'text-white/40' : 'text-gray-500'
                    }`}>
                      {row.avg}s
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* AREA CHART */}
        <div className={`p-6 rounded-xl border col-span-1 md:col-span-2 h-[380px] ${
          darkMode 
            ? 'bg-white/3 border-white/6' 
            : 'bg-white border-gray-200 shadow-sm'
        }`}>
          <h3 className={`text-sm font-medium mb-6 ${
            darkMode ? 'text-white/70' : 'text-gray-700'
          }`}>
            Token Volume
          </h3>
          
          <ResponsiveContainer width="100%" height="85%">
            <AreaChart data={data.daily_trend}>
              <defs>
                <linearGradient id="colorTokens" x1="0" y1="0" x2="0" y2="1">
                  <stop 
                    offset="5%" 
                    stopColor={darkMode ? "rgba(255,255,255,0.3)" : "rgba(0,0,0,0.15)"} 
                    stopOpacity={1}
                  />
                  <stop 
                    offset="95%" 
                    stopColor={darkMode ? "rgba(255,255,255,0)" : "rgba(0,0,0,0)"} 
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid 
                strokeDasharray="3 3" 
                stroke={COLORS.grid} 
                vertical={false} 
              />
              <XAxis 
                dataKey="date" 
                stroke={COLORS.text} 
                fontSize={11} 
                tickLine={false} 
                axisLine={false}
                tickMargin={10}
              />
              <YAxis 
                stroke={COLORS.text} 
                fontSize={11} 
                tickLine={false} 
                axisLine={false} 
              />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: darkMode ? 'rgba(0, 0, 0, 0.9)' : 'rgba(255, 255, 255, 0.95)', 
                  backdropFilter: 'blur(10px)',
                  border: darkMode ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
                  borderRadius: '8px',
                  boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
                  fontSize: '12px'
                }}
                labelStyle={{ 
                  color: darkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.7)',
                  marginBottom: '4px'
                }}
                itemStyle={{ 
                  color: darkMode ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.9)' 
                }}
              />
              <Area 
                type="monotone" 
                dataKey="tokens" 
                stroke={darkMode ? "rgba(255,255,255,0.5)" : "rgba(0,0,0,0.4)"} 
                strokeWidth={2}
                fillOpacity={1} 
                fill="url(#colorTokens)" 
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

      </div>
    </div>
  );
}

const PresetButton = ({ label, onClick, darkMode }) => (
  <button 
    onClick={onClick}
    className={`px-3 py-2 rounded-lg text-xs font-medium transition-all ${
      darkMode 
        ? 'text-white/50 hover:text-white/80 hover:bg-white/8' 
        : 'text-gray-500 hover:text-gray-700 hover:bg-black/5'
    }`}
  >
    {label}
  </button>
);