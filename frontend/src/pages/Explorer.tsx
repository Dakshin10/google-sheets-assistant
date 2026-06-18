import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useReactTable, getCoreRowModel, flexRender } from '@tanstack/react-table';
import { Database, RefreshCw, Eye, EyeOff, ChevronRight, Layers } from 'lucide-react';

export function Explorer() {
  const [selectedTable, setSelectedTable] = useState('');
  const [showMetadata, setShowMetadata] = useState(false);

  // 1. Fetch connections to build spreadsheet → tables mapping
  const { data: connections = [] } = useQuery<any[]>({
    queryKey: ['connections'],
    queryFn: async () => {
      const res = await fetch('/api/connections');
      if (!res.ok) throw new Error('Failed to fetch connections');
      return res.json();
    }
  });

  // 2. Fetch all available tables
  const { data: tables = [], isLoading: loadingTables, refetch: refetchTables } = useQuery<string[]>({
    queryKey: ['explorer_tables'],
    queryFn: async () => {
      const res = await fetch('/api/explorer/tables');
      if (!res.ok) throw new Error('Failed to fetch explorer tables');
      return res.json();
    }
  });

  // 3. Group tables by their parent spreadsheet connection
  const groupedTables = useMemo(() => {
    const groups: { conn: any; tables: string[] }[] = [];
    const assignedTables = new Set<string>();

    for (const conn of connections) {
      const prefix = conn.spreadsheet_name
        ? conn.spreadsheet_name.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '').toLowerCase().replace(/_+/g, '_').replace(/^_|_$/g, '')
        : '';
      const matched = tables.filter(t => prefix && t.startsWith(prefix + '_'));
      matched.forEach(t => assignedTables.add(t));
      if (matched.length > 0) {
        groups.push({ conn, tables: matched });
      }
    }

    // Unassigned tables (orphans or unknown)
    const unassigned = tables.filter(t => !assignedTables.has(t));
    if (unassigned.length > 0) {
      groups.push({ conn: { spreadsheet_name: 'Other Tables', id: -1 }, tables: unassigned });
    }

    return groups;
  }, [connections, tables]);

  // Auto-select first table when available
  React.useEffect(() => {
    if (tables.length > 0) {
      if (!selectedTable || !tables.includes(selectedTable)) {
        setSelectedTable(tables[0]);
      }
    } else {
      setSelectedTable('');
    }
  }, [tables, selectedTable]);

  // 4. Fetch selected table data
  const { data: tableData = { columns: [], rows: [] }, isLoading: loadingData, refetch: refetchData } = useQuery({
    queryKey: ['explorer_table_data', selectedTable],
    queryFn: async () => {
      if (!selectedTable) return { columns: [], rows: [] };
      const res = await fetch(`/api/explorer/tables/${encodeURIComponent(selectedTable)}`);
      if (!res.ok) throw new Error('Failed to fetch table contents');
      return res.json();
    },
    enabled: !!selectedTable
  });

  // 5. Filter metadata columns
  const metadataCols = ['_row_index', '_row_hash', 'is_deleted', 'deleted_at'];
  const displayColumns = useMemo(() => {
    return tableData.columns.filter((col: string) => showMetadata || !metadataCols.includes(col));
  }, [tableData.columns, showMetadata]);

  // 6. Friendly name: worksheet part of the table name
  const getFriendlyTableName = (tableName: string, conn: any) => {
    if (!conn || conn.id === -1) return tableName;
    const prefix = conn.spreadsheet_name
      ? conn.spreadsheet_name.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '').toLowerCase().replace(/_+/g, '_').replace(/^_|_$/g, '')
      : '';
    if (prefix && tableName.startsWith(prefix + '_')) {
      const worksheetPart = tableName.slice(prefix.length + 1);
      return worksheetPart.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }
    return tableName;
  };

  // TanStack table setup
  const columns = useMemo(() => {
    return displayColumns.map((colName: string) => ({
      accessorKey: colName,
      header: colName.replace(/_/g, ' ').toUpperCase(),
      cell: (info: any) => {
        const val = info.getValue();
        if (val === null || val === undefined) return <span className="text-gray-600 font-mono italic">NULL</span>;
        if (typeof val === 'boolean') return val ? 'true' : 'false';
        return String(val);
      }
    }));
  }, [displayColumns]);

  const data = useMemo(() => tableData.rows, [tableData.rows]);
  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel() });

  // Find which connection the selected table belongs to
  const selectedConn = useMemo(() => {
    for (const g of groupedTables) {
      if (g.tables.includes(selectedTable)) return g.conn;
    }
    return null;
  }, [groupedTables, selectedTable]);

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Database Explorer</h1>
          <p className="text-gray-400 mt-1">Browse rows and columns stored inside your synced tables.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { refetchTables(); if (selectedTable) refetchData(); }}
            className="p-2 bg-white/5 hover:bg-white/10 rounded-xl border border-white/5 text-gray-300 hover:text-white transition"
            title="Refresh"
          >
            <RefreshCw size={18} />
          </button>
          <button
            onClick={() => setShowMetadata(!showMetadata)}
            className="flex items-center gap-2 bg-white/5 hover:bg-white/10 text-sm text-gray-300 hover:text-white px-4 py-2 rounded-xl border border-white/5 transition"
          >
            {showMetadata ? <EyeOff size={16} /> : <Eye size={16} />}
            <span>{showMetadata ? 'Hide Metadata' : 'Show Metadata'}</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
        {/* Table Selector Sidebar — grouped by spreadsheet */}
        <div className="glass p-5 rounded-2xl lg:col-span-1 space-y-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <Database size={16} className="text-indigo-400" /> Synced Tables
          </h3>
          <div className="space-y-3 mt-2">
            {loadingTables ? (
              <div className="text-sm text-gray-500 py-4 text-center">Loading tables...</div>
            ) : groupedTables.length === 0 ? (
              <div className="text-sm text-gray-500 py-8 text-center">No tables yet. Connect a sheet first.</div>
            ) : groupedTables.map((group, gi) => (
              <div key={gi} className="space-y-1">
                {/* Spreadsheet group header */}
                <div className="flex items-center gap-2 px-2 py-1">
                  <Layers size={12} className="text-indigo-400 flex-shrink-0" />
                  <span className="text-[11px] font-bold text-indigo-400 uppercase tracking-wider truncate">
                    {group.conn.spreadsheet_name}
                  </span>
                </div>
                {group.tables.map((t: string) => (
                  <button
                    key={t}
                    onClick={() => setSelectedTable(t)}
                    className={`w-full text-left px-3 py-2 rounded-xl text-sm font-medium transition flex items-center gap-2 ${
                      selectedTable === t
                        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                        : 'text-gray-400 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    <ChevronRight size={12} className="flex-shrink-0" />
                    <span className="truncate">{getFriendlyTableName(t, group.conn)}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* Table Content View */}
        <div className="glass p-6 rounded-2xl lg:col-span-3 min-h-[400px] flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-white">
                {selectedTable
                  ? getFriendlyTableName(selectedTable, selectedConn)
                  : 'Select a Table'}
              </h2>
              {selectedTable && selectedConn && selectedConn.id !== -1 && (
                <p className="text-xs text-gray-500 mt-0.5">
                  From: <span className="text-indigo-400">{selectedConn.spreadsheet_name}</span>
                  {' '}· Raw table: <code className="text-gray-600 font-mono">{selectedTable}</code>
                </p>
              )}
            </div>
            {selectedTable && (
              <span className="text-xs text-gray-400 bg-white/5 px-2.5 py-1 rounded-full">
                {tableData.rows.length} rows loaded (Limit 500)
              </span>
            )}
          </div>

          {loadingData ? (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              Loading table contents...
            </div>
          ) : selectedTable ? (
            <div className="flex-1 flex flex-col">
              <div className="overflow-x-auto border border-white/5 rounded-xl">
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    {table.getHeaderGroups().map(headerGroup => (
                      <tr key={headerGroup.id} className="bg-white/5 text-gray-300 border-b border-white/5">
                        {headerGroup.headers.map(header => (
                          <th key={header.id} className="px-4 py-3 font-semibold text-xs tracking-wider whitespace-nowrap">
                            {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                          </th>
                        ))}
                      </tr>
                    ))}
                  </thead>
                  <tbody className="divide-y divide-white/5 text-gray-300">
                    {table.getRowModel().rows.map(row => (
                      <tr key={row.id} className="hover:bg-white/5 transition">
                        {row.getVisibleCells().map(cell => (
                          <td
                            key={cell.id}
                            className="px-4 py-3 font-medium whitespace-nowrap text-xs max-w-[200px] truncate"
                            title={String(cell.getValue() ?? '')}
                          >
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {data.length === 0 && (
                      <tr>
                        <td colSpan={columns.length || 1} className="py-12 text-center text-gray-500">
                          Table is empty or has no data yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-500 gap-2">
              <Database size={32} className="text-gray-600" />
              <span>Select a table from the sidebar to browse.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
