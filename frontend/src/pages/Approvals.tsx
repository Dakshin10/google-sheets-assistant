import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Shield, Sparkles, CheckCircle, XCircle, AlertCircle, Terminal } from 'lucide-react';

export function Approvals() {
  const queryClient = useQueryClient();

  // Fetch pending schema changes
  const { data: schemaChanges = [], isLoading: loadingSchema } = useQuery<any[]>({
    queryKey: ['pending_schema_changes'],
    queryFn: async () => {
      const res = await fetch('/api/schema/pending');
      if (!res.ok) throw new Error('Failed to fetch schema changes');
      return res.json();
    }
  });

  // Fetch pending modifying query approvals
  const { data: sqlQueries = [], isLoading: loadingSQL } = useQuery<any[]>({
    queryKey: ['pending_query_approvals'],
    queryFn: async () => {
      const res = await fetch('/api/query/pending');
      if (!res.ok) throw new Error('Failed to fetch SQL approvals');
      return res.json();
    }
  });

  // Mutate: Approve schema change
  const approveSchemaMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/schema/approve/${id}`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to approve schema change');
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending_schema_changes'] });
      queryClient.invalidateQueries({ queryKey: ['connections'] });
    }
  });

  // Mutate: Reject schema change
  const rejectSchemaMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/schema/reject/${id}`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to reject schema change');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending_schema_changes'] });
      queryClient.invalidateQueries({ queryKey: ['connections'] });
    }
  });

  // Mutate: Approve & Execute SQL Query
  const approveSQLMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`/api/query/approve/${id}`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to approve SQL query');
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending_query_approvals'] });
      queryClient.invalidateQueries({ queryKey: ['logs'] });
    }
  });

  // Mutate: Reject SQL Query
  const rejectSQLMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`/api/query/reject/${id}`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to reject SQL query');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending_query_approvals'] });
    }
  });

  // Render detail formatter for schema change JSON
  const renderDetails = (detailsStr: string, type: string) => {
    try {
      const details = JSON.parse(detailsStr);
      if (type === 'RENAME') {
        return (
          <span>
            Rename column <code className="bg-white/10 px-1 py-0.5 rounded text-indigo-400 font-mono text-xs">{details.old_name}</code> to{' '}
            <code className="bg-white/10 px-1 py-0.5 rounded text-emerald-400 font-mono text-xs">{details.new_name}</code>
          </span>
        );
      } else if (type === 'TYPE_CHANGE') {
        return (
          <span>
            Change type of <code className="bg-white/10 px-1 py-0.5 rounded text-indigo-400 font-mono text-xs">{details.column}</code> from{' '}
            <code className="bg-white/10 px-1 py-0.5 rounded text-rose-400 font-mono text-xs">{details.old_type}</code> to{' '}
            <code className="bg-white/10 px-1 py-0.5 rounded text-emerald-400 font-mono text-xs">{details.new_type}</code>
          </span>
        );
      }
      return detailsStr;
    } catch {
      return detailsStr;
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white">Approvals Hub</h1>
        <p className="text-gray-400 mt-1">Review schema drifts (renames & type evolutions) or authorize write queries.</p>
      </div>

      {/* Schema Evolutions Inbox */}
      <div className="glass p-6 rounded-2xl space-y-4">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Shield size={20} className="text-amber-400" /> Pending Schema Evolution Modifications
        </h2>
        <p className="text-sm text-gray-400">
          Sync scheduling is automatically suspended for sheets experiencing schema drifts until these changes are approved or rejected.
        </p>

        <div className="overflow-x-auto pt-2">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/5 text-gray-400">
                <th className="pb-3 font-semibold">Change ID</th>
                <th className="pb-3 font-semibold">Sheet Connection</th>
                <th className="pb-3 font-semibold">Worksheet</th>
                <th className="pb-3 font-semibold">Evolution Type</th>
                <th className="pb-3 font-semibold">Change Details</th>
                <th className="pb-3 font-semibold">Requested At</th>
                <th className="pb-3 font-semibold text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-gray-300">
              {loadingSchema ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-500">
                    Loading pending schema changes...
                  </td>
                </tr>
              ) : schemaChanges.map((change: any) => (
                <tr key={change.id} className="hover:bg-white/5 transition">
                  <td className="py-4 font-mono text-xs">{change.id}</td>
                  <td className="py-4 font-semibold text-white">{change.spreadsheet_name}</td>
                  <td className="py-4 text-xs text-gray-400">{change.worksheet_title}</td>
                  <td className="py-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                        change.change_type === 'RENAME'
                          ? 'bg-indigo-500/10 text-indigo-400'
                          : 'bg-rose-500/10 text-rose-400'
                      }`}
                    >
                      {change.change_type}
                    </span>
                  </td>
                  <td className="py-4 text-xs">{renderDetails(change.details, change.change_type)}</td>
                  <td className="py-4 text-xs text-gray-400">{new Date(change.created_at).toLocaleString()}</td>
                  <td className="py-4">
                    <div className="flex items-center justify-center gap-3">
                      <button
                        onClick={() => approveSchemaMutation.mutate(change.id)}
                        disabled={approveSchemaMutation.isPending}
                        className="flex items-center gap-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 px-3 py-1 rounded-xl text-xs font-semibold border border-emerald-500/15 transition disabled:opacity-40"
                      >
                        <CheckCircle size={14} /> Approve
                      </button>
                      <button
                        onClick={() => rejectSchemaMutation.mutate(change.id)}
                        disabled={rejectSchemaMutation.isPending}
                        className="flex items-center gap-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 px-3 py-1 rounded-xl text-xs font-semibold border border-rose-500/15 transition disabled:opacity-40"
                      >
                        <XCircle size={14} /> Reject
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {schemaChanges.length === 0 && !loadingSchema && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Sparkles className="text-emerald-400/60" size={24} />
                      <span>No pending schema alterations. Sync engine is active.</span>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* SQL Modifying Write Query Queue */}
      <div className="glass p-6 rounded-2xl space-y-4">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Terminal size={20} className="text-rose-400" /> Modifying Database Write Queries (SQL Overrides)
        </h2>
        <p className="text-sm text-gray-400">
          For security, any natural language instruction generating modifying write operations (INSERT, UPDATE, DELETE, DROP) is queued for manual administrator sign-off.
        </p>

        <div className="space-y-4 pt-2">
          {loadingSQL ? (
            <div className="text-center text-gray-500 py-8">Loading queries...</div>
          ) : sqlQueries.map((req: any) => (
            <div key={req.request_id} className="bg-white/5 border border-white/5 rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-gray-300">
                  <span className="font-semibold text-white">{req.request_id}</span> •
                  <span className="text-xs text-gray-400">Requested by:</span>
                  <span className="bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded text-xs">{req.user}</span> •
                  <span className="text-xs text-gray-400">Time:</span>
                  <span className="text-xs">{req.created_at}</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => approveSQLMutation.mutate(req.request_id)}
                    disabled={approveSQLMutation.isPending}
                    className="flex items-center gap-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 px-3.5 py-1.5 rounded-xl text-xs font-bold border border-emerald-500/15 transition disabled:opacity-40"
                  >
                    <CheckCircle size={14} /> Approve & Execute
                  </button>
                  <button
                    onClick={() => rejectSQLMutation.mutate(req.request_id)}
                    disabled={rejectSQLMutation.isPending}
                    className="flex items-center gap-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 px-3.5 py-1.5 rounded-xl text-xs font-bold border border-rose-500/15 transition disabled:opacity-40"
                  >
                    <XCircle size={14} /> Reject
                  </button>
                </div>
              </div>

              {/* SQL Code Block */}
              <div className="bg-black/45 border border-white/5 rounded-xl p-4 font-mono text-sm text-emerald-300/90 overflow-x-auto whitespace-pre-wrap">
                {req.generated_sql}
              </div>
            </div>
          ))}
          {sqlQueries.length === 0 && !loadingSQL && (
            <div className="text-center text-gray-500 py-8 border border-dashed border-white/5 rounded-2xl">
              <div className="flex flex-col items-center justify-center gap-2">
                <Shield className="text-emerald-400/40" size={24} />
                <span>No pending SQL write approvals. All systems secured.</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
