import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, RefreshCw, CheckCircle, XCircle, Clock } from 'lucide-react';

export function Logs() {
  const [filterId, setFilterId] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch connections for the dropdown filter
  const { data: connections = [] } = useQuery<any[]>({
    queryKey: ['connections'],
    queryFn: async () => {
      const res = await fetch('/api/connections');
      if (!res.ok) throw new Error('Failed to fetch connections');
      return res.json();
    }
  });

  // Fetch sync logs, optionally filtered by sheet_id
  const { data: logs = [], isLoading, refetch } = useQuery<any[]>({
    queryKey: ['logs', filterId],
    queryFn: async () => {
      const url = filterId ? `/api/logs?sheet_id=${filterId}` : '/api/logs';
      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to fetch sync logs');
      return res.json();
    }
  });

  // Local search filter
  const filteredLogs = logs.filter((log: any) => {
    const query = searchQuery.toLowerCase();
    if (!query) return true;
    const sheetName = (log.spreadsheet_name || '').toLowerCase();
    const errorMsg = (log.error_message || '').toLowerCase();
    const status = (log.status || '').toLowerCase();
    return sheetName.includes(query) || errorMsg.includes(query) || status.includes(query);
  });

  const formatDuration = (start: string, finish: string) => {
    if (!start || !finish) return '—';
    const ms = new Date(finish).getTime() - new Date(start).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Sync Audit Logs</h1>
          <p className="text-gray-400 mt-1">Full audit logs of all background synchronization events.</p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 bg-white/5 hover:bg-white/10 text-sm text-gray-300 hover:text-white px-4 py-2 rounded-xl border border-white/5 transition"
        >
          <RefreshCw size={16} />
          <span>Refresh Logs</span>
        </button>
      </div>

      {/* Filters Panel */}
      <div className="glass p-5 rounded-2xl glow-primary">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          {/* Sheet dropdown filter */}
          <div className="space-y-1">
            <label className="text-xs text-gray-400 font-semibold">Filter by Sheet</label>
            <select
              value={filterId}
              onChange={(e) => setFilterId(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition cursor-pointer"
            >
              <option value="">All Sheets</option>
              {connections.map((conn: any) => (
                <option key={conn.id} value={conn.id}>
                  {conn.spreadsheet_name} (ID {conn.id})
                </option>
              ))}
            </select>
          </div>

          {/* Text search */}
          <div className="space-y-1">
            <label className="text-xs text-gray-400 font-semibold">Search (name, status, error)</label>
            <input
              type="text"
              placeholder="e.g. success, error description"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition"
            />
          </div>

          <button
            onClick={() => refetch()}
            className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition flex items-center justify-center gap-2"
          >
            <Search size={16} /> Apply Filters
          </button>
        </div>
      </div>

      {/* Stats Summary */}
      {filteredLogs.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="glass p-4 rounded-xl">
            <p className="text-xs text-gray-400">Total Logs</p>
            <p className="text-2xl font-bold text-white mt-1">{filteredLogs.length}</p>
          </div>
          <div className="glass p-4 rounded-xl">
            <p className="text-xs text-gray-400">Successful</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">
              {filteredLogs.filter((l: any) => l.status === 'SUCCESS').length}
            </p>
          </div>
          <div className="glass p-4 rounded-xl">
            <p className="text-xs text-gray-400">Failed</p>
            <p className="text-2xl font-bold text-rose-400 mt-1">
              {filteredLogs.filter((l: any) => l.status !== 'SUCCESS').length}
            </p>
          </div>
        </div>
      )}

      {/* Logs Table */}
      <div className="glass p-6 rounded-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/5 text-gray-400">
                <th className="pb-3 font-semibold">Log ID</th>
                <th className="pb-3 font-semibold">Sheet Connection</th>
                <th className="pb-3 font-semibold">Sync Started</th>
                <th className="pb-3 font-semibold">Sync Finished</th>
                <th className="pb-3 font-semibold text-center">Duration</th>
                <th className="pb-3 font-semibold text-center">Row Metrics (+ / ~ / -)</th>
                <th className="pb-3 font-semibold">Status</th>
                <th className="pb-3 font-semibold">Details / Errors</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-gray-300">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-gray-500">Loading sync logs...</td>
                </tr>
              ) : filteredLogs.map((log: any) => (
                <tr key={log.id} className="hover:bg-white/5 transition">
                  <td className="py-4 font-mono text-xs text-gray-500">{log.id}</td>
                  <td className="py-4">
                    <div className="font-semibold text-white">{log.spreadsheet_name || `Sheet ID ${log.sheet_id}`}</div>
                    <div className="text-xs text-gray-500">ID: {log.sheet_id}</div>
                  </td>
                  <td className="py-4 text-xs text-gray-400">{new Date(log.sync_started).toLocaleString()}</td>
                  <td className="py-4 text-xs text-gray-400">{new Date(log.sync_finished).toLocaleString()}</td>
                  <td className="py-4 text-center">
                    <span className="flex items-center justify-center gap-1 text-xs text-gray-400">
                      <Clock size={12} />
                      {formatDuration(log.sync_started, log.sync_finished)}
                    </span>
                  </td>
                  <td className="py-4 text-center font-mono text-xs">
                    <span className="text-emerald-400">+{log.rows_added ?? 0}</span>{' / '}
                    <span className="text-indigo-400">~{log.rows_updated ?? 0}</span>{' / '}
                    <span className="text-rose-400">-{log.rows_deleted ?? 0}</span>
                  </td>
                  <td className="py-4">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                      log.status === 'SUCCESS'
                        ? 'bg-emerald-500/10 text-emerald-400'
                        : 'bg-rose-500/10 text-rose-400'
                    }`}>
                      {log.status === 'SUCCESS' ? <CheckCircle size={12} /> : <XCircle size={12} />}
                      {log.status}
                    </span>
                  </td>
                  <td className="py-4 text-xs max-w-[250px] truncate" title={log.error_message || ''}>
                    {log.error_message ? (
                      <span className="text-rose-400">{log.error_message}</span>
                    ) : (
                      <span className="text-gray-500 italic">No errors</span>
                    )}
                  </td>
                </tr>
              ))}
              {filteredLogs.length === 0 && !isLoading && (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-gray-500">
                    No sync logs found. Connect a sheet to start syncing.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
