'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, TrendingUp, AlertTriangle, CheckCircle, XCircle, Search, Calendar } from 'lucide-react';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

// --- Types ---
type Trade = {
  symbol: string;
  ltp: number;
  close: number;
  stop_loss: number;
  target: number;
  ema_9: number;
  ema_20: number;
  spread_pct?: number;
  is_mtf?: boolean;
  is_stage2?: boolean;
  note?: string;
};

type RejectedTrade = {
  symbol: string;
  reason: string;
};

type LogMessage = {
  type: 'status' | 'progress' | 'match_found' | 'error' | 'complete';
  message?: string;
  value?: number;
  current_symbol?: string;
  data?: Trade;
  valid_count?: number;
  rejected_count?: number;
  valid_trades?: Trade[];
};

// --- Utils ---
function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

// --- Components ---

const Card = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <div className={cn("bg-slate-800/50 border border-slate-700/50 backdrop-blur-xl rounded-2xl p-6 shadow-xl", className)}>
    {children}
  </div>
);

const Badge = ({ children, type }: { children: React.ReactNode; type: 'green' | 'red' | 'blue' | 'yellow' }) => {
  const colors = {
    green: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    red: "bg-rose-500/10 text-rose-400 border-rose-500/20",
    blue: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    yellow: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  };
  return (
    <span className={cn("px-2.5 py-0.5 rounded-full text-xs font-medium border", colors[type])}>
      {children}
    </span>
  );
};

export default function Dashboard() {
  const [date, setDate] = useState('2026-01-01');
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('Ready');
  const [currentSymbol, setCurrentSymbol] = useState('');

  const [validTrades, setValidTrades] = useState<Trade[]>([]);
  const [rejectedTrades, setRejectedTrades] = useState<RejectedTrade[]>([]);
  const [logs, setLogs] = useState<string[]>([]);

  const logsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const runBacktest = async () => {
    setIsRunning(true);
    setProgress(0);
    setValidTrades([]);
    setRejectedTrades([]);
    setLogs(['Starting backtest...']);
    setStatus('Initializing...');

    // Use env var or default to localhost
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    try {
      const response = await fetch(`${API_URL}/run-backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const msg: LogMessage = JSON.parse(line);
            handleMessage(msg);
          } catch (e) {
            console.error("Parse Error", e, line);
          }
        }
      }
    } catch (error) {
      console.error(error);
      setStatus('Connection Failed');
    } finally {
      setIsRunning(false);
      setProgress(100);
      setStatus('Complete');
    }
  };

  const handleMessage = (msg: LogMessage) => {
    if (msg.type === 'status') {
      setStatus(msg.message || '');
      setLogs(prev => [...prev, `[STATUS] ${msg.message}`]);
    } else if (msg.type === 'progress') {
      setProgress(msg.value || 0);
      setCurrentSymbol(msg.current_symbol || '');
      setStatus(msg.message || '');
    } else if (msg.type === 'match_found') {
      if (msg.data) {
        setValidTrades(prev => [...prev, msg.data!]);
        setLogs(prev => [...prev, `[MATCH] Found ${msg.data!.symbol}`]);
      }
    } else if (msg.type === 'error') {
      setLogs(prev => [...prev, `[ERROR] ${msg.message}`]);
    } else if (msg.type === 'complete') {
      if (msg.valid_trades) {
        // Ensure we have final list 
      }
      setLogs(prev => [...prev, `[COMPLETE] Finished.`]);
    }
  };

  // Calculations for UI match
  const getChangePct = (ltp: number, close: number) => {
    if (!close) return 0;
    return ((ltp - close) / close) * 100;
  };
  const getTargetDist = (target: number, ltp: number) => {
    if (!ltp) return 0;
    return ((target - ltp) / ltp) * 100;
  };
  const getSLDist = (sl: number, ltp: number) => {
    if (!ltp) return 0;
    return ((sl - ltp) / ltp) * 100;
  };
  const formatDate = (d: string) => {
    if (!d) return '--/--/----';
    const parts = d.split('-');
    if (parts.length !== 3) return d;
    const [y, m, dstr] = parts;
    return `${dstr}/${m}/${y}`;
  };

  return (
    <div className="min-h-screen bg-[#0B1120] text-slate-100 font-sans selection:bg-indigo-500/30">

      {/* Header */}
      <header className="fixed top-0 w-full z-50 bg-[#0B1120]/90 backdrop-blur-md border-b border-white/5">
        <div className="max-w-[1600px] mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/20 rounded-lg">
              <TrendingUp className="w-6 h-6 text-indigo-400" />
            </div>
            <h1 className="text-xl font-bold text-white">
              Swing Scanner
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-xs text-slate-500 font-mono">
              v2.1.0 • Pro
            </div>
          </div>
        </div>
      </header>

      <main className="pt-24 pb-20 max-w-[1600px] mx-auto px-6 space-y-6">

        {/* Controls Section */}
        <section className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <Card className="lg:col-span-1 space-y-4 !bg-slate-900/50">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Backtest Date</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full bg-[#0F172A] border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
              />
            </div>

            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              onClick={runBacktest}
              disabled={isRunning}
              className={cn(
                "w-full py-3 rounded-lg font-semibold text-sm flex items-center justify-center gap-2 transition-all",
                isRunning
                  ? "bg-slate-800 text-slate-500 cursor-not-allowed"
                  : "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20"
              )}
            >
              {isRunning ? (
                <>Run Scan...</>
              ) : (
                <> <Play className="w-4 h-4 fill-current" /> Run Scan </>
              )}
            </motion.button>

            {/* Progress Bar */}
            {isRunning && (
              <div className="space-y-1">
                <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-blue-500"
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ type: "spring", stiffness: 50 }}
                  />
                </div>
              </div>
            )}
          </Card>

          {/* Metrics */}
          <Card className="lg:col-span-3 !bg-slate-900/50 flex items-center justify-around">
            <div className="text-center">
              <div className="text-3xl font-bold text-white">{validTrades.length}</div>
              <div className="text-xs text-emerald-400 font-medium uppercase tracking-wider mt-1">Valid Setups</div>
            </div>
            <div className="w-px h-12 bg-white/5" />
            <div className="text-center">
              <div className="text-3xl font-bold text-slate-500">{rejectedTrades.length}</div>
              <div className="text-xs text-rose-500/50 font-medium uppercase tracking-wider mt-1">Rejected</div>
            </div>
          </Card>
        </section>

        {/* Live Logs */}
        <div className="h-32 bg-black/30 border-y border-white/5 font-mono text-xs p-4 overflow-y-auto custom-scrollbar">
          {logs.map((log, i) => (
            <div key={i} className="text-slate-500 border-l border-slate-800 pl-2 mb-1">{log}</div>
          ))}
          <div ref={logsEndRef} />
        </div>

        {/* Results Table */}
        <section>
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2 text-white">
            Valid Opportunities
            <span className="text-xs font-normal text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">{validTrades.length}</span>
          </h2>

          <div className="bg-[#0F172A] border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[#131C2E] border-b border-slate-700/50">
                    <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Date</th>
                    <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Symbol</th>
                    <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Close <span className="text-[10px] normal-case opacity-50 block text-slate-500">(As of {formatDate(date)})</span>
                    </th>
                    <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Live LTP</th>
                    <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Next Target</th>
                    <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Stop Loss</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  <AnimatePresence>
                    {validTrades.map((trade) => {
                      const ltpChange = getChangePct(trade.ltp, trade.close);
                      const targetDist = getTargetDist(trade.target, trade.ltp);
                      const slDist = getSLDist(trade.stop_loss, trade.ltp);

                      return (
                        <motion.tr
                          key={trade.symbol}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          className="hover:bg-slate-800/30 transition-colors group"
                        >
                          <td className="p-4 text-sm text-slate-400 font-mono">
                            {formatDate(date)}
                          </td>
                          <td className="p-4">
                            <div className="flex flex-col gap-1.5">
                              <div className="flex items-center gap-2">
                                <a
                                  href={`https://in.tradingview.com/chart/?symbol=NSE:${trade.symbol}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="font-bold text-blue-400 text-lg hover:text-blue-300 hover:underline transition-all"
                                >
                                  {trade.symbol}
                                </a>
                                {trade.note === 'New' && (
                                  <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded uppercase font-bold tracking-wider">New</span>
                                )}
                              </div>
                              <div className="flex items-center gap-2">
                                {trade.is_mtf && <span className="text-[10px] font-bold text-yellow-500 uppercase tracking-wider">MTF</span>}
                                {trade.is_stage2 && (
                                  <span className="text-[10px] text-emerald-400 border border-emerald-500/30 bg-emerald-500/5 px-1.5 rounded uppercase font-medium">Stage 2</span>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="p-4 text-base text-slate-200 tabular-nums">
                            {trade.close.toFixed(2)}
                          </td>
                          <td className="p-4">
                            <div className="flex flex-col">
                              <span className="text-base text-slate-200 tabular-nums">{trade.ltp}</span>
                              <span className={cn("text-xs font-bold tabular-nums", ltpChange >= 0 ? "text-emerald-400" : "text-rose-400")}>
                                {ltpChange >= 0 ? "+" : ""}{ltpChange.toFixed(2)}%
                              </span>
                            </div>
                          </td>
                          <td className="p-4">
                            <div className="flex flex-col gap-1">
                              <span className="text-base text-slate-200 tabular-nums">{trade.target}</span>
                              <div className="flex items-center gap-2">
                                <span className={cn("text-xs font-bold tabular-nums", targetDist >= 0 ? "text-emerald-400" : "text-emerald-400")}>
                                  {targetDist > 0 ? "+" : ""}{targetDist.toFixed(2)}%
                                </span>
                                {targetDist <= 0 && <span className="text-[10px] text-emerald-500 font-bold uppercase tracking-wider">Target Hit</span>}
                              </div>
                            </div>
                          </td>
                          <td className="p-4">
                            <div className="flex flex-col">
                              <span className="text-base text-slate-200 tabular-nums">{trade.stop_loss}</span>
                              <span className="text-xs font-bold text-rose-400 tabular-nums">
                                {slDist.toFixed(2)}%
                              </span>
                            </div>
                          </td>
                        </motion.tr>
                      )
                    })}
                  </AnimatePresence>
                  {validTrades.length === 0 && !isRunning && (
                    <tr>
                      <td colSpan={6} className="p-12 text-center text-slate-600 font-mono text-sm">
                                    // No results found yet. Run a scan?
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

      </main>
    </div>
  );
}
