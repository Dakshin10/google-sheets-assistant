import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Play, Pause, RefreshCw, Trash2, Plus, ShieldAlert, Database, AlertCircle } from 'lucide-react';

export function Connections() {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState('');
  const [freq, setFreq] = useState(5);
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [disconnectSheetId, setDisconnectSheetId] = useState<number | null>(null);
  const [deleteData, setDeleteData] = useState(false);

  // Fetch connections
  const { data: connections = [], isLoading } = useQuery<any[]>({
    queryKey: ['connections'],
    queryFn: async () => {
      const res = await fetch('/api/connections');
      if (!res.ok) throw new Error('Failed to fetch connections');
      return res.json();
    }
  });

  // Fetch tables to show count per sheet
  const { data: allTables = [] } = useQuery<string[]>({
    queryKey: ['explorer_tables'],
    queryFn: async () => {
      const res = await fetch('/api/explorer/tables');
      if (!res.ok) return [];
      return res.json();
    }
  });

  // Count tables per spreadsheet
  const getTableCount = (conn: any) => {
    if (!conn?.spreadsheet_name) return 0;
    const prefix = conn.spreadsheet_name
      .replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '').toLowerCase()
      .replace(/_+/g, '_').replace(/^_|_$/g, '');
    return allTables.filter(t => t.startsWith(prefix + '_')).length;
  };

  // Connect sheet
  const connectMutation = useMutation({
    mutationFn: async (payload: { url: string; sync_frequency_minutes: number; owner_email: string }) => {
      const res = await fetch('/api/connections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to connect sheet');
      return data;
    },
    onSuccess: (data) => {
      setMessage({ type: 'success', text: data.message });
      setUrl(''); setEmail(''); setFreq(5);
      queryClient.invalidateQueries({ queryKey: ['connections'] });
      queryClient.invalidateQueries({ queryKey: ['explorer_tables'] });
    },
    onError: (err: any) => setMessage({ type: 'error', text: err.message || 'Error connecting sheet' })
  });

  // Pause sync
  const pauseMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/connections/${id}/pause`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to pause');
      return res.json();
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['connections'] })
  });

  // Resume sync
  const resumeMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/connections/${id}/resume`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to resume');
      return res.json();
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['connections'] })
  });

  // Force sync
  const forceSyncMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/connections/${id}/sync`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to trigger sync');
      return res.json();
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['connections'] })
  });

  // Disconnect
  const disconnectMutation = useMutation({
    mutationFn: async ({ id, deleteData }: { id: number; deleteData: boolean }) => {
      const res = await fetch(`/api/connections/${id}?delete_data=${deleteData}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to disconnect');
      return res.json();
    },
    onSuccess: () => {
      setDisconnectSheetId(null);
      setDeleteData(false);
      queryClient.invalidateQueries({ queryKey: ['connections'] });
      queryClient.invalidateQueries({ queryKey: ['explorer_tables'] });
      queryClient.invalidateQueries({ queryKey: ['explorer_table_data'] });
      queryClient.invalidateQueries({ queryKey: ['logs'] });
    }
  });

  // Cleanup orphan tables
  const cleanupMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/admin/cleanup-orphan-tables', { method: 'POST' });
      if (!res.ok) throw new Error('Failed to cleanup');
      return res.json();
    },
    onSuccess: (data) => {
      setMessage({ type: 'success', text: data.message || 'Cleanup complete.' });
      queryClient.invalidateQueries({ queryKey: ['explorer_tables'] });
      queryClient.invalidateQueries({ queryKey: ['explorer_table_data'] });
    },
    onError: (err: any) => setMessage({ type: 'error', text: err.message })
  });

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    setMessage(null);
    connectMutation.mutate({ url, sync_frequency_minutes: freq, owner_email: email });
  };

  const statusStyle = (status: string) => {
    if (status === 'ACTIVE') return 'bg-emerald-500/10 text-emerald-400';
    if (status === 'SYNCING') return 'bg-indigo-500/10 text-indigo-400 animate-pulse';
    if (status === 'PAUSED') return 'bg-zinc-500/10 text-zinc-400';
    if (status === 'SCHEMA_SUSPENDED') return 'bg-amber-500/10 text-amber-400';
    return 'bg-rose-500/10 text-rose-400';
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white">Sheet Connections</h1>
        <p className="text-gray-400 mt-1">Register Google Sheet URLs, adjust configurations, and control scheduler runs.</p>
      </div>

      {/* Connect Form */}
      <div className="glass p-6 rounded-2xl glow-primary">
        <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <Plus size={20} className="text-indigo-400" /> Connect a Google Sheet
        </h2>
        <form onSubmit={handleConnect} className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs text-gray-400 font-semibold">Google Sheet URL</label>
              <input
                type="text"
                placeholder="https://docs.google.com/spreadsheets/d/.../edit"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-gray-400 font-semibold">Owner Email (optional)</label>
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition"
              />
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between items-center text-xs text-gray-400">
              <span className="font-semibold">Sync Frequency: every {freq} minute{freq > 1 ? 's' : ''}</span>
              <span>1 min - 60 min</span>
            </div>
            <input
              type="range" min="1" max="60" value={freq}
              onChange={(e) => setFreq(parseInt(e.target.value))}
              className="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
          </div>

          <div className="flex justify-between items-center pt-2">
            <div>
              {message && (
                <div className={`text-sm font-medium flex items-center gap-2 ${message.type === 'success' ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {message.type === 'error' && <AlertCircle size={14} />}
                  {message.text}
                </div>
              )}
            </div>
            <button
              type="submit"
              disabled={connectMutation.isPending}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/40 text-white text-sm font-semibold px-5 py-2 rounded-xl transition flex items-center gap-2"
            >
              {connectMutation.isPending ? (
                <><RefreshCw size={14} className="animate-spin" /> Connecting...</>
              ) : (
                'Connect & Sync'
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Connections Table */}
      <div className="glass p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white">Active Connection Registries</h2>
          <button
            onClick={() => cleanupMutation.mutate()}
            disabled={cleanupMutation.isPending}
            title="Drop tables from disconnected sheets"
            className="flex items-center gap-2 text-xs text-zinc-400 hover:text-rose-400 bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg border border-white/5 transition"
          >
            <Database size={13} />
            {cleanupMutation.isPending ? 'Cleaning...' : 'Cleanup Orphan Tables'}
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/5 text-gray-400">
                <th className="pb-3 font-semibold">ID</th>
                <th className="pb-3 font-semibold">Sheet Name</th>
                <th className="pb-3 font-semibold">Spreadsheet ID</th>
                <th className="pb-3 font-semibold">Owner</th>
                <th className="pb-3 font-semibold">Frequency</th>
                <th className="pb-3 font-semibold">Tables</th>
                <th className="pb-3 font-semibold">Last Sync</th>
                <th className="pb-3 font-semibold">Status</th>
                <th className="pb-3 font-semibold text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-gray-300">
              {isLoading ? (
                <tr><td colSpan={9} className="py-8 text-center text-gray-500">Loading registries...</td></tr>
              ) : connections.map((conn: any) => (
                <tr key={conn.id} className="hover:bg-white/5 transition">
                  <td className="py-4 font-mono text-xs text-gray-500">{conn.id}</td>
                  <td className="py-4 font-semibold text-white">{conn.spreadsheet_name}</td>
                  <td className="py-4 font-mono text-xs text-gray-400 max-w-[150px] truncate" title={conn.spreadsheet_id}>
                    {conn.spreadsheet_id}
                  </td>
                  <td className="py-4 text-xs text-gray-400">{conn.owner_email || 'unknown'}</td>
                  <td className="py-4 text-xs">{conn.sync_frequency_minutes}m</td>
                  <td className="py-4 text-xs">
                    <span className="flex items-center gap-1 text-indigo-400">
                      <Database size={12} />
                      {getTableCount(conn)} table{getTableCount(conn) !== 1 ? 's' : ''}
                    </span>
                  </td>
                  <td className="py-4 text-xs text-gray-400">
                    {conn.last_successful_sync
                      ? new Date(conn.last_successful_sync).toLocaleString()
                      : <span className="text-gray-600 italic">Never</span>}
                  </td>
                  <td className="py-4">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${statusStyle(conn.sync_status)}`}>
                      {conn.sync_status}
                    </span>
                  </td>
                  <td className="py-4">
                    <div className="flex items-center justify-center gap-2">
                      {conn.sync_enabled ? (
                        <button
                          onClick={() => pauseMutation.mutate(conn.id)}
                          title="Pause Synchronization"
                          className="p-1.5 hover:bg-white/5 rounded-lg text-gray-400 hover:text-amber-400 transition"
                        >
                          <Pause size={16} />
                        </button>
                      ) : (
                        <button
                          onClick={() => resumeMutation.mutate(conn.id)}
                          title="Resume Synchronization"
                          className="p-1.5 hover:bg-white/5 rounded-lg text-gray-400 hover:text-emerald-400 transition"
                        >
                          <Play size={16} />
                        </button>
                      )}
                      <button
                        onClick={() => forceSyncMutation.mutate(conn.id)}
                        title="Force Immediate Sync"
                        disabled={conn.sync_status === 'SYNCING'}
                        className="p-1.5 hover:bg-white/5 rounded-lg text-gray-400 hover:text-indigo-400 transition disabled:opacity-30"
                      >
                        <RefreshCw size={16} className={conn.sync_status === 'SYNCING' ? 'animate-spin' : ''} />
                      </button>
                      <button
                        onClick={() => setDisconnectSheetId(conn.id)}
                        title="Disconnect Registry"
                        className="p-1.5 hover:bg-white/5 rounded-lg text-gray-400 hover:text-rose-400 transition"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {connections.length === 0 && !isLoading && (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-gray-500">
                    No connected sheets found. Start by entering a Google Sheets URL above.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Disconnect Modal */}
      {disconnectSheetId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="glass max-w-md w-full p-6 rounded-2xl border border-white/10 space-y-6">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-rose-500/10 text-rose-400 rounded-xl">
                <ShieldAlert size={24} />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Disconnect Registry</h3>
                <p className="text-sm text-gray-400 mt-1">
                  This will stop all sync jobs for this sheet. Recurring scheduled tasks will be cancelled.
                </p>
              </div>
            </div>

            <div className="bg-white/5 p-4 rounded-xl border border-white/5 space-y-2">
              <label className="flex items-center gap-3 cursor-pointer text-sm text-gray-200">
                <input
                  type="checkbox"
                  checked={deleteData}
                  onChange={(e) => setDeleteData(e.target.checked)}
                  className="rounded border-white/10 bg-white/5 text-indigo-600 focus:ring-indigo-500"
                />
                <span>Also drop all synced database tables</span>
              </label>
              <p className="text-xs text-gray-400 pl-8">
                If checked, all historical data stored in D1 for this sheet will be permanently deleted.
              </p>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => { setDisconnectSheetId(null); setDeleteData(false); }}
                className="px-4 py-2 hover:bg-white/5 border border-white/10 rounded-xl text-sm text-gray-300 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => disconnectMutation.mutate({ id: disconnectSheetId, deleteData })}
                disabled={disconnectMutation.isPending}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 disabled:bg-rose-600/40 text-white rounded-xl text-sm font-semibold transition"
              >
                {disconnectMutation.isPending ? 'Disconnecting...' : 'Disconnect'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
