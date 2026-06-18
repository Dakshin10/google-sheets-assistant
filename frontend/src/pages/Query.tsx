import React, { useState, useMemo } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useReactTable, getCoreRowModel, flexRender } from '@tanstack/react-table';
import { Sparkles, Terminal, Copy, Check, Clock, AlertTriangle, ShieldCheck, Database } from 'lucide-react';

export function Query() {
  const [question, setQuestion] = useState('');
  const [selectedSheetId, setSelectedSheetId] = useState('');
  const [copied, setCopied] = useState(false);
  const [result, setResult] = useState<any | null>(null);

  // Fetch connections list for the dropdown selector
  const { data: connections = [] } = useQuery<any[]>({
    queryKey: ['connections'],
    queryFn: async () => {
      const res = await fetch('/api/connections');
      if (!res.ok) throw new Error('Failed to fetch connections');
      return res.json();
    }
  });

  // Mutation: POST user query with sheet scoping
  const queryMutation = useMutation({
    mutationFn: async (payload: { question: string; sheet_id?: number }) => {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Query execution failed');
      }
      return res.json();
    },
    onSuccess: (data) => {
      setResult(data);
    }
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setResult(null);
    queryMutation.mutate({
      question,
      sheet_id: selectedSheetId ? parseInt(selectedSheetId) : undefined
    });
  };

  const handleCopySql = () => {
    if (!result?.sql) return;
    navigator.clipboard.writeText(result.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Build TanStack Table definitions for query rows/columns
  const columns = useMemo(() => {
    if (!result?.columns) return [];
    return result.columns.map((colName: string) => ({
      accessorKey: colName,
      header: colName.replace(/_/g, ' ').toUpperCase(),
      cell: (info: any) => {
        const val = info.getValue();
        if (val === null || val === undefined) {
          return <span className="text-gray-600 font-mono italic">NULL</span>;
        }
        if (typeof val === 'boolean') {
          return val ? 'true' : 'false';
        }
        return String(val);
      }
    }));
  }, [result?.columns]);

  const data = useMemo(() => result?.rows || [], [result?.rows]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white">NLP Query Console</h1>
        <p className="text-gray-400 mt-1">Ask questions in plain English and automatically execute SQLite queries.</p>
      </div>

      {/* English Prompt Input */}
      <div className="glass p-6 rounded-2xl glow-primary">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <label className="text-sm text-gray-300 font-semibold flex items-center gap-2">
              <Sparkles size={16} className="text-indigo-400" /> Enter your question
            </label>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 font-medium">Scoping Filter:</span>
              <select
                value={selectedSheetId}
                onChange={(e) => setSelectedSheetId(e.target.value)}
                className="bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 transition cursor-pointer"
              >
                <option value="">All Connected Sheets (RAG dynamic context)</option>
                {connections.map((conn: any) => (
                  <option key={conn.id} value={conn.id}>
                    {conn.spreadsheet_name} (ID {conn.id})
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-2">
            <textarea
              rows={3}
              placeholder="e.g. What is the average price of products with stock greater than 50?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-2xl p-4 text-sm text-white focus:outline-none focus:border-indigo-500 transition resize-none"
            />
          </div>
          <div className="flex justify-between items-center">
            <span className="text-xs text-gray-500">
              Generated queries auto-filter soft-deleted rows.
            </span>
            <button
              type="submit"
              disabled={queryMutation.isPending}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/40 text-white text-sm font-semibold px-6 py-2.5 rounded-xl transition flex items-center gap-2 shadow-lg shadow-indigo-600/20"
            >
              {queryMutation.isPending ? 'Generating SQL...' : 'Run Query'}
            </button>
          </div>
        </form>
      </div>

      {queryMutation.isError && (
        <div className="bg-rose-500/10 border border-rose-500/15 rounded-2xl p-4 flex items-start gap-3 text-rose-400">
          <AlertTriangle className="mt-0.5 flex-shrink-0" size={18} />
          <div>
            <h4 className="font-bold text-sm">Query Pipeline Error</h4>
            <p className="text-xs mt-1 text-rose-400/80">{queryMutation.error.message}</p>
          </div>
        </div>
      )}

      {/* Query Outcomes Panel */}
      {result && (
        <div className="space-y-6 animate-fadeIn">
          {/* Metadata Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="glass-card p-4 rounded-xl flex items-center gap-3">
              <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg">
                <Clock size={18} />
              </div>
              <div>
                <p className="text-xs text-gray-400">Pipeline Latency</p>
                <p className="text-sm font-bold text-white mt-0.5">{result.duration_ms} ms</p>
              </div>
            </div>

            <div className="glass-card p-4 rounded-xl flex items-center gap-3">
              <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg">
                <Database size={18} />
              </div>
              <div>
                <p className="text-xs text-gray-400">Result Metrics</p>
                <p className="text-sm font-bold text-white mt-0.5">{data.length} rows returned</p>
              </div>
            </div>

            <div className="glass-card p-4 rounded-xl flex items-center gap-3">
              <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg">
                <Sparkles size={18} />
              </div>
              <div>
                <p className="text-xs text-gray-400">Cache Strategy</p>
                <p className="text-sm font-bold text-white mt-0.5">
                  {result.cache_hit ? 'Cache Hit' : 'Database Executed'}
                </p>
              </div>
            </div>
          </div>

          {/* Generated SQL Code Block */}
          <div className="glass p-5 rounded-2xl space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Terminal size={16} className="text-indigo-400" /> Generated SQL Statement
              </h3>
              <button
                onClick={handleCopySql}
                className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition"
              >
                {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <pre className="bg-black/45 border border-white/5 rounded-xl p-4 font-mono text-sm text-indigo-300 overflow-x-auto whitespace-pre-wrap">
              {result.sql}
            </pre>
            {result.explanation && (
              <div className="text-xs text-gray-400 pl-1">
                <span className="font-semibold text-gray-300">Explanation:</span> {result.explanation}
              </div>
            )}
          </div>

          {/* Conditional Query Action Results */}
          {result.status === 'ERROR' ? (
            <div className="bg-rose-500/10 border border-rose-500/15 rounded-2xl p-5 flex items-start gap-4 text-rose-400">
              <AlertTriangle className="mt-0.5 flex-shrink-0" size={24} />
              <div>
                <h4 className="font-bold text-sm">Database Execution Failure</h4>
                <pre className="text-xs mt-2 font-mono bg-black/30 p-3 rounded-lg text-rose-300 overflow-x-auto whitespace-pre-wrap">
                  {result.error}
                </pre>
              </div>
            </div>
          ) : (
            /* Results Dataframe Table rendering */
            <div className="glass p-6 rounded-2xl space-y-4">
              <h3 className="text-sm font-bold text-white">Execution Result Table</h3>
              {data.length > 0 ? (
                <div className="overflow-x-auto border border-white/5 rounded-xl">
                  <table className="w-full text-left border-collapse text-sm">
                    <thead>
                      {table.getHeaderGroups().map(headerGroup => (
                        <tr key={headerGroup.id} className="bg-white/5 text-gray-300 border-b border-white/5">
                          {headerGroup.headers.map(header => (
                            <th key={header.id} className="px-4 py-3 font-semibold text-xs tracking-wider whitespace-nowrap">
                              {flexRender(header.column.columnDef.header, header.getContext())}
                            </th>
                          ))}
                        </tr>
                      ))}
                    </thead>
                    <tbody className="divide-y divide-white/5 text-gray-300">
                      {table.getRowModel().rows.map(row => (
                        <tr key={row.id} className="hover:bg-white/5 transition">
                          {row.getVisibleCells().map(cell => (
                            <td key={cell.id} className="px-4 py-3 font-medium text-xs whitespace-nowrap">
                              {flexRender(cell.column.columnDef.cell, cell.getContext())}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500 italic">
                  Query executed successfully, but returned 0 rows.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
