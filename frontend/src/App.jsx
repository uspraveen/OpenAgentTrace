import React, { useState, useEffect } from 'react';
import ReactFlow, { Background, Controls, useNodesState, useEdgesState, MarkerType } from 'reactflow';
import 'reactflow/dist/style.css';
import axios from 'axios';
import { Layers, Sun, Moon, Trash2, X, Activity, Server, Database, Cpu, Zap } from 'lucide-react';
import MetricsDashboard from './MetricsDashboard';

const API_URL = "http://127.0.0.1:8000";

export default function App() {
  const [view, setView] = useState('traces'); // 'traces' or 'analytics'
  const [traces, setTraces] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [selectedTrace, setSelectedTrace] = useState(null);
  const [darkMode, setDarkMode] = useState(true);
  
  // React Flow State
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [inspectorData, setInspectorData] = useState(null);

  // Analytics Filters State
  const [filterParams, setFilterParams] = useState({});

  // 1. Toggle Dark Mode
  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode);
  }, [darkMode]);

  // 2. Data Fetching Logic (Pure: Does not update filter state)
  const fetchData = async (currentParams = {}) => {
    try {
      // A. Fetch Traces
      const tRes = await axios.get(`${API_URL}/traces`);
      setTraces(tRes.data);
      
      // B. Fetch Analytics with Params
      const query = new URLSearchParams(currentParams).toString();
      const aRes = await axios.get(`${API_URL}/analytics/dashboard?${query}`);
      setAnalytics(aRes.data);
      
    } catch (e) { console.error("API Error", e); }
  };

  // 3. Poll for Data
  useEffect(() => {
    // Initial fetch
    fetchData(filterParams);

    // Poll every 5 seconds using current filters
    const interval = setInterval(() => {
      fetchData(filterParams);
    }, 5000);

    return () => clearInterval(interval);
  }, [filterParams]); // Re-run if filters change

  // 4. Handle Filter Updates from Dashboard
  const handleRefresh = (newParams) => {
    if (newParams) {
      // Update state, which triggers useEffect -> fetchData
      setFilterParams(prev => ({ ...prev, ...newParams }));
    } else {
      // Just re-fetch without changing filters
      fetchData(filterParams);
    }
  };

  // 5. Handle Delete Trace
  const handleDeleteTrace = async (e, id) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this trace?")) return;
    try {
      await axios.delete(`${API_URL}/traces/${id}`);
      setTraces(prev => prev.filter(t => t.trace_id !== id));
      if (selectedTrace === id) {
        setSelectedTrace(null);
        setNodes([]);
        setEdges([]);
      }
      // Re-fetch analytics as metrics might change
      fetchData(filterParams);
    } catch (err) { console.error("Failed to delete", err); }
  };

  // 6. Load Graph when Trace Selected
  useEffect(() => {
    if (!selectedTrace) return;
    const loadGraph = async () => {
      try {
        const res = await axios.get(`${API_URL}/traces/${selectedTrace}`);
        const spans = res.data;
        
        const nodeBg = darkMode ? 'rgba(30, 41, 59, 0.8)' : 'rgba(255, 255, 255, 0.9)';
        const nodeColor = darkMode ? '#fff' : '#000';
        const borderColor = darkMode ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.1)';

        const newNodes = spans.map((s, i) => ({
          id: s.span_id,
          data: { ...s, label: s.name },
          position: { x: i * 220, y: s.parent_span_id ? 150 + (i * 60) : 50 },
          style: {
            background: nodeBg, 
            color: nodeColor, 
            border: s.status === 'FAILURE' ? '1px solid #EF4444' : `1px solid ${borderColor}`,
            backdropFilter: 'blur(10px)',
            padding: '12px', 
            borderRadius: '12px', 
            minWidth: '160px',
            fontSize: '12px',
            boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.15)'
          }
        }));

        const newEdges = spans.filter(s => s.parent_span_id).map(s => ({
          id: `e-${s.span_id}`, source: s.parent_span_id, target: s.span_id,
          type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed },
          style: { stroke: darkMode ? '#666' : '#999' }
        }));

        setNodes(newNodes);
        setEdges(newEdges);
      } catch (e) {}
    };
    loadGraph();
  }, [selectedTrace, darkMode]);

  return (
    <div className={`flex h-screen overflow-hidden font-sans transition-colors duration-500 ${
      darkMode 
      ? 'bg-gradient-to-br from-gray-900 via-slate-900 to-black text-white' 
      : 'bg-gradient-to-br from-gray-100 via-blue-50 to-white text-gray-900'
    } animate-gradient`}>
      
      {/* SIDEBAR (GLASS PANEL) */}
      <div className="w-72 flex flex-col glass-panel z-20">
        <div className="p-5 border-b border-white/10 flex justify-between items-center">
          <h1 className="text-lg font-bold tracking-tight flex items-center gap-2">
            <Activity className="text-cyan-400" size={20} /> 
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-500">
              AgentTracer
            </span>
          </h1>
          <button onClick={() => setDarkMode(!darkMode)} className="p-2 rounded-full hover:bg-white/10 transition">
            {darkMode ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
        
        <div className="flex gap-2 p-3">
          <TabButton active={view === 'traces'} onClick={() => setView('traces')} label="Traces" icon={<Layers size={14}/>} />
          <TabButton active={view === 'analytics'} onClick={() => setView('analytics')} label="Analytics" icon={<Zap size={14}/>} />
        </div>

        {/* TRACE LIST */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {traces.map(t => (
            <div key={t.trace_id} 
              onClick={() => { setView('traces'); setSelectedTrace(t.trace_id); }}
              className={`group p-3 rounded-xl cursor-pointer border transition-all duration-200 relative ${
                selectedTrace === t.trace_id 
                ? 'bg-cyan-500/10 border-cyan-500/50 shadow-[0_0_15px_rgba(6,182,212,0.15)]' 
                : 'hover:bg-white/5 border-transparent hover:border-white/10'
              }`}>
              
              <div className="flex justify-between items-start">
                <div className="font-medium text-sm truncate w-40">{t.name}</div>
                <button 
                  onClick={(e) => handleDeleteTrace(e, t.trace_id)}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition"
                  title="Delete Trace"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              
              <div className="text-xs opacity-60 flex justify-between mt-2">
                <span>{new Date(t.start_time).toLocaleTimeString()}</span>
                <span className={t.status==='SUCCESS'?'text-emerald-400':'text-rose-400 font-bold'}>{t.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 relative z-10">
        {view === 'analytics' ? (
          <MetricsDashboard 
            data={analytics} 
            darkMode={darkMode} 
            onRefresh={handleRefresh} 
          />
        ) : (
          <ReactFlow nodes={nodes} edges={edges} onNodeClick={(_, n) => setInspectorData(n.data)} fitView>
            <Background color={darkMode ? "#555" : "#ccc"} gap={25} size={1} />
            <Controls className="glass rounded-lg overflow-hidden border-white/10 text-black dark:text-white" />
          </ReactFlow>
        )}
      </div>

      {/* INSPECTOR PANEL */}
      {view === 'traces' && inspectorData && (
        <div className="w-96 glass-panel p-6 overflow-y-auto shadow-2xl z-30 absolute right-0 top-0 bottom-0 border-l border-white/10">
          <div className="flex justify-between items-center mb-6">
            <div className="flex items-center gap-2">
              <NodeTypeIcon type={inspectorData.type} />
              <h2 className="text-lg font-bold truncate">{inspectorData.name}</h2>
            </div>
            <button onClick={() => setInspectorData(null)} className="hover:text-rose-400"><X size={18}/></button>
          </div>
          
          <DataSection title="Metadata" data={inspectorData.meta} />
          <DataSection title="Inputs" data={inspectorData.inputs} />
          <DataSection title="Outputs" data={inspectorData.outputs} />
          
          {inspectorData.error_message && (
            <div className="bg-rose-500/10 border border-rose-500/30 p-4 rounded-xl text-rose-300 text-sm mt-4">
              <div className="font-bold mb-1 flex items-center gap-2"><X size={14}/> Error Trace</div>
              {inspectorData.error_message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// --- SUB COMPONENTS ---

const TabButton = ({ active, onClick, label, icon }) => (
  <button onClick={onClick} className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2 ${
      active ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-900/50' : 'hover:bg-white/5 opacity-70 hover:opacity-100'
    }`}>
    {icon} {label}
  </button>
);

const NodeTypeIcon = ({ type }) => {
  if (type === 'llm') return <Cpu size={16} className="text-purple-400"/>;
  if (type === 'db') return <Database size={16} className="text-amber-400"/>;
  if (type === 'vector_db') return <Server size={16} className="text-emerald-400"/>;
  return <Activity size={16} className="text-blue-400"/>;
};

const DataSection = ({ title, data }) => {
  if (!data || Object.keys(data).length === 0) return null;
  return (
    <div className="mb-6">
      <h3 className="text-xs font-bold opacity-50 uppercase mb-2 tracking-wider">{title}</h3>
      <pre className="p-4 rounded-xl text-xs overflow-x-auto bg-black/20 border border-white/5 font-mono text-cyan-100 leading-relaxed">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
};