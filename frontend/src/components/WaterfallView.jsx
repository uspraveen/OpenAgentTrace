import React from 'react';
import { Clock, AlertCircle } from 'lucide-react';

export default function WaterfallView({ spans, darkMode, onSpanClick }) {
    if (!spans || spans.length === 0) return <div className="p-10 text-center opacity-50">No spans to display</div>;

    // 1. Calculate Timeline Bounds
    const startTime = Math.min(...spans.map(s => s.start_time));
    const endTime = Math.max(...spans.map(s => s.end_time || s.start_time));
    const totalDuration = endTime - startTime;

    // 2. Sort spans by start time for waterfall effect
    const sortedSpans = [...spans].sort((a, b) => a.start_time - b.start_time);

    return (
        <div className={`p-6 overflow-y-auto h-full ${darkMode ? 'text-gray-200' : 'text-gray-800'}`}>
            <div className="mb-4 flex justify-between items-center">
                <h2 className="text-xl font-bold flex items-center gap-2">
                    <Clock size={20} className="text-cyan-400" /> Execution Timeline
                </h2>
                <div className="text-xs opacity-50 font-mono">
                    Total Duration: {(totalDuration * 1000).toFixed(2)}ms
                </div>
            </div>

            <div className="relative space-y-1">
                {/* Timestamp Ruler (Simplified) */}
                <div className="flex justify-between text-[10px] opacity-30 border-b border-gray-500/20 pb-1 mb-2">
                    <span>0ms</span>
                    <span>{(totalDuration * 1000).toFixed(0)}ms</span>
                </div>

                {sortedSpans.map((span) => {
                    const startOffset = span.start_time - startTime;
                    const duration = span.duration || 0;

                    // Current span stats
                    const leftPct = (startOffset / totalDuration) * 100;
                    const widthPct = Math.max((duration / totalDuration) * 100, 0.5); // Min width 0.5% for visibility

                    // Color coding by type
                    let colorClass = "bg-blue-500";
                    if (span.type === 'llm') colorClass = "bg-purple-500";
                    if (span.type === 'db') colorClass = "bg-amber-500";
                    if (span.type === 'vector_db') colorClass = "bg-emerald-500";
                    if (span.status === 'FAILURE') colorClass = "bg-rose-500";

                    return (
                        <div
                            key={span.span_id}
                            className="group flex items-center gap-3 hover:bg-white/5 p-1 rounded cursor-pointer transition"
                            onClick={() => onSpanClick(span)}
                        >
                            {/* Label Column */}
                            <div className="w-48 text-xs truncate font-medium text-right opacity-70 group-hover:opacity-100">
                                {span.name}
                            </div>

                            {/* Bar Column */}
                            <div className="flex-1 relative h-6 bg-gray-500/5 rounded-sm overflow-hidden">
                                <div
                                    className={`absolute h-full rounded-sm opacity-80 group-hover:opacity-100 transition-all ${colorClass}`}
                                    style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                                >
                                    {span.status === 'FAILURE' && (
                                        <AlertCircle size={12} className="text-white absolute -right-4 top-1" />
                                    )}
                                </div>
                            </div>

                            {/* Duration Label */}
                            <div className="w-16 text-[10px] opacity-50 font-mono text-left">
                                {(duration * 1000).toFixed(1)}ms
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
