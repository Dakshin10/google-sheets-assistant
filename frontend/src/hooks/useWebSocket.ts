import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';

export function useWebSocket() {
  const queryClient = useQueryClient();
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    function connect() {
      // Determine WebSocket protocol (ws or wss)
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      // Proxy route /api/ws will direct to backend WS port
      const wsUrl = `${protocol}//${window.location.host}/api/ws`;
      
      console.log(`Connecting to WebSocket: ${wsUrl}`);
      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('Received WebSocket event:', message);
          
          const { event: eventType, data } = message;
          
          // Invalidate React Query cache keys based on event type
          if (eventType === 'connection_change') {
            queryClient.invalidateQueries({ queryKey: ['connections'] });
            queryClient.invalidateQueries({ queryKey: ['explorer_tables'] });
            queryClient.invalidateQueries({ queryKey: ['explorer_table_data'] });
          } else if (eventType === 'sync_status' || eventType === 'sync_status_change') {
            queryClient.invalidateQueries({ queryKey: ['connections'] });
            queryClient.invalidateQueries({ queryKey: ['logs'] });
            queryClient.invalidateQueries({ queryKey: ['stats'] });
            queryClient.invalidateQueries({ queryKey: ['explorer_tables'] });
            queryClient.invalidateQueries({ queryKey: ['explorer_table_data'] });
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      socket.onclose = () => {
        console.log('WebSocket connection closed. Attempting reconnect in 3s...');
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 3000);
      };

      socket.onerror = (err) => {
        console.error('WebSocket encountered error:', err);
        socket.close();
      };
    }

    connect();

    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [queryClient]);

  return socketRef.current;
}
