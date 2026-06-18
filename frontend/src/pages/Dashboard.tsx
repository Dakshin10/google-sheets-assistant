import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Database, Link2, AlertTriangle, Activity, Terminal, TrendingUp, CheckCircle, Clock } from 'lucide-react';

interface DashboardProps {
  setActiveTab: (tab: string) => void;
}

export function Dashboard({ setActiveTab }: DashboardProps) {
  const { data: connections = [] } = useQuery<any[]>({
    queryKey: ['connections'],
    queryFn: async () => {
      const res = await fetch('/api/connections');
      if (!res.ok) throw new Error('Failed to fetch connections');
      return res.json();
    }
  });

  const { data: logs = [] } = useQuery<any[]>({
    queryKey: ['logs'],
    queryFn: async () => {
      const res = await fetch('/api/logs');
      if (!res.ok) throw new Error('Failed to fetch logs');
      return res.json();
    }
  });

  const activeSheetsCount = connections.filter(c => c.sync_enabled && c.sync_status === 'ACTIVE').length;
  const syncingSheetsCount = connections.filter(c => c.sync_status === 'SYNCING').length;
  const errorSheetsCount = connections.filter(c => ['AUTH_ERROR', 'NETWORK_ERROR', 'FAILED'].includes(c.sync_status)).length;

  // Total rows synced across all logs
  const totalRowsAdded = logs.reduce((sum: number, l: any) => sum + (l.rows_added || 0), 0);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white">System Dashboard</h1>
        <p className="text-gray-400 mt-1">Real-time status of your Google Sheets and D1 Database integrations.</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
        <div className="glass p-6 rounded-2xl glow-primary">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400 font-medium">Connected Sheets</p>
              <h3 className="text-3xl font-bold text-white mt-1">{connections.length}</h3>
            </div>
            <div className="p-3 bg-indigo-500/10 rounded-xl text-indigo-400">
              <Link2 size={24} />
            </div>
          </div>
          <div className="mt-4 text-xs text-gray-500">
            <span className="text-emerald-400 font-semibold">{activeSheetsCount} active</span>
            {syncingSheetsCount > 0 && <> • <span className="text-indigo-400">{syncingSheetsCount} syncing</span></>}
          </div>
        </div>

        <div className="glass p-6 rounded-2xl glow-primary">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400 font-medium">Active Sync Jobs</p>
              <h3 className="text-3xl font-bold text-white mt-1">{connections.filter(c => c.sync_enabled).length}</h3>
            </div>
            <div className="p-3 bg-indigo-500/10 rounded-xl text-indigo-400">
              <Activity size={24} />
            </div>
          </div>
          <div className="mt-4 text-xs text-gray-500">Scheduled background sync tasks</div>
        </div>

        <div className="glass p-6 rounded-2xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400 font-medium">Total Rows Synced</p>
              <h3 className="text-3xl font-bold text-white mt-1">{totalRowsAdded.toLocaleString()}</h3>
            </div>
            <div className="p-3 bg-emerald-500/10 rounded-xl text-emerald-400">
              <TrendingUp size={24} />
            </div>
          </div>
          <div className="mt-4 text-xs text-gray-500">Cumulative rows added to D1</div>
        </div>

        <div className="glass p-6 rounded-2xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400 font-medium">System Issues</p>
              <h3 className="text-3xl font-bold text-white mt-1">{errorSheetsCount}</h3>
            </div>
            <div className={`p-3 rounded-xl ${errorSheetsCount > 0 ? 'bg-rose-500/10 text-rose-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
              <AlertTriangle size={24} />
            </div>
          </div>
          <div className="mt-4 text-xs text-gray-500">
            {errorSheetsCount > 0 ? (
              <span className="text-rose-400 font-semibold">Check auth credentials</span>
            ) : (
              <span className="text-emerald-400">Sync services healthy</span>
            )}
          </div>
        </div>
      </div>

      {/* Connected Sheets Status + Recent Logs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Quick Actions */}
        <div className="glass p-6 rounded-2xl space-y-4 lg:col-span-1">
          <h2 className="text-lg font-bold text-white">Quick Management</h2>
          <p className="text-sm text-gray-400">Shortcuts to common operations.</p>
          <div className="space-y-3 mt-4">
            <button
              onClick={() => setActiveTab('connections')}
              className="w-full flex items-center justify-between p-3 rounded-xl bg-white/5 hover:bg-white/10 transition border border-white/5 text-sm text-gray-200"
            >
              <span>Connect new Google Sheet</span>
              <Link2 size={16} />
            </button>
            <button
              onClick={() => setActiveTab('query')}
              className="w-full flex items-center justify-between p-3 rounded-xl bg-white/5 hover:bg-white/10 transition border border-white/5 text-sm text-gray-200"
            >
              <span>NLP SQL Assistant Console</span>
              <Terminal size={16} />
            </button>
            <button
              onClick={() => setActiveTab('explorer')}
              className="w-full flex items-center justify-between p-3 rounded-xl bg-white/5 hover:bg-white/10 transition border border-white/5 text-sm text-gray-200"
            >
              <span>Database Table Explorer</span>
              <Database size={16} />
            </button>
          </div>

          {/* Per-sheet status summary */}
          {connections.length > 0 && (
            <div className="mt-4 pt-4 border-t border-white/5 space-y-2">
              <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Sheet Status</p>
              {connections.map((conn: any) => (
                <div key={conn.id} className="flex items-center justify-between py-1">
                  <span className="text-xs text-gray-300 truncate max-w-[130px]">{conn.spreadsheet_name}</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    conn.sync_status === 'ACTIVE' ? 'bg-emerald-500/10 text-emerald-400' :
                    conn.sync_status === 'SYNCING' ? 'bg-indigo-500/10 text-indigo-400' :
                    conn.sync_status === 'PAUSED' ? 'bg-zinc-500/10 text-zinc-400' :
                    'bg-rose-500/10 text-rose-400'
                  }`}>
                    {conn.sync_status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Sync Operations */}
        <div className="glass p-6 rounded-2xl lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white">Recent Sync Operations</h2>
            <button onClick={() => setActiveTab('logs')} className="text-xs text-indigo-400 hover:text-indigo-300 font-medium">
              View All Logs
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-white/5 text-gray-400">
                  <th className="pb-3 font-semibold">Sheet</th>
                  <th className="pb-3 font-semibold">Finished</th>
                  <th className="pb-3 font-semibold text-center">Changes (+ / ~ / -)</th>
                  <th className="pb-3 font-semibold text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-gray-300">
                {logs.slice(0, 6).map((log: any) => (
                  <tr key={log.id} className="hover:bg-white/5 transition">
                    <td className="py-3">
                      <div className="font-medium text-white text-sm">
                        {log.spreadsheet_name || `Sheet ${log.sheet_id}`}
                      </div>
                    </td>
                    <td className="py-3 text-xs text-gray-400 flex items-center gap-1 mt-1">
                      <Clock size={11} />
                      {new Date(log.sync_finished).toLocaleTimeString()}
                    </td>
                    <td className="py-3 text-center font-mono text-xs">
                      <span className="text-emerald-400">+{log.rows_added ?? 0}</span>{' / '}
                      <span className="text-indigo-400">~{log.rows_updated ?? 0}</span>{' / '}
                      <span className="text-rose-400">-{log.rows_deleted ?? 0}</span>
                    </td>
                    <td className="py-3 text-right">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
                        log.status === 'SUCCESS'
                          ? 'bg-emerald-500/10 text-emerald-400'
                          : 'bg-rose-500/10 text-rose-400'
                      }`}>
                        {log.status === 'SUCCESS' ? <CheckCircle size={11} /> : <AlertTriangle size={11} />}
                        {log.status}
                      </span>
                    </td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-gray-500">
                      No sync operations yet. Connect a sheet to get started.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
