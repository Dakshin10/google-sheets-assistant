import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Dashboard } from './pages/Dashboard';
import { Connections } from './pages/Connections';
import { Query } from './pages/Query';
import { Explorer } from './pages/Explorer';
import { Logs } from './pages/Logs';
import { useWebSocket } from './hooks/useWebSocket';
import { 
  LayoutDashboard, 
  Link2, 
  ShieldCheck, 
  Terminal, 
  Database, 
  History, 
  Cable 
} from 'lucide-react';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function AppContent() {
  const [activeTab, setActiveTab] = useState('dashboard');
  
  // Initialize WebSocket connections for real-time invalidations
  useWebSocket();

  // Navigation config
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'connections', label: 'Connections', icon: Link2 },
    { id: 'query', label: 'Query Console', icon: Terminal },
    { id: 'explorer', label: 'Explorer', icon: Database },
    { id: 'logs', label: 'Audit Logs', icon: History },
  ];

  return (
    <div className="flex h-screen bg-[#0a0a0e] text-zinc-100 overflow-hidden font-sans">
      {/* Sidebar Navigation */}
      <aside className="w-64 border-r border-zinc-800 bg-[#0d0d12]/80 flex flex-col backdrop-blur-md">
        <div className="p-6 flex items-center gap-3 border-b border-zinc-800">
          <div className="p-2 bg-indigo-600/10 text-indigo-400 rounded-xl">
            <Cable size={22} />
          </div>
          <div>
            <h1 className="text-base font-bold text-white leading-none">Sheets → D1</h1>
            <p className="text-[10px] text-zinc-500 font-semibold tracking-wider uppercase mt-1">SaaS Platform</p>
          </div>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                    : 'text-zinc-400 hover:text-white hover:bg-white/5'
                }`}
              >
                <Icon size={18} className={isActive ? 'text-white' : 'text-zinc-500'} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-zinc-800 text-[10px] text-zinc-600 font-semibold text-center uppercase tracking-wider">
          v1.0.0 Stable
        </div>
      </aside>

      {/* Main Content Pane */}
      <main className="flex-1 flex flex-col overflow-y-auto bg-gradient-to-br from-[#0a0a0e] via-[#0d0d14] to-[#0a0a0e]">
        <div className="max-w-6xl w-full mx-auto px-8 py-10">
          {activeTab === 'dashboard' && <Dashboard setActiveTab={setActiveTab} />}
          {activeTab === 'connections' && <Connections />}
          {activeTab === 'query' && <Query />}
          {activeTab === 'explorer' && <Explorer />}
          {activeTab === 'logs' && <Logs />}
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}
