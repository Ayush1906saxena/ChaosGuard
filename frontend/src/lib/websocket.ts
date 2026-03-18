import { ScanProgressUpdate } from './types';

type MessageHandler = (update: ScanProgressUpdate) => void;
type StatusHandler = (connected: boolean) => void;
type ConnectionFailedHandler = () => void;

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8080';

export class ScanWebSocket {
  private ws: WebSocket | null = null;
  private scanId: string;
  private onMessage: MessageHandler;
  private onStatusChange: StatusHandler;
  private onConnectionFailed?: ConnectionFailedHandler;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionallyClosed = false;

  constructor(
    scanId: string,
    onMessage: MessageHandler,
    onStatusChange: StatusHandler,
    onConnectionFailed?: ConnectionFailedHandler
  ) {
    this.scanId = scanId;
    this.onMessage = onMessage;
    this.onStatusChange = onStatusChange;
    this.onConnectionFailed = onConnectionFailed;
  }

  connect(): void {
    this.intentionallyClosed = false;
    this.reconnectAttempts = 0;
    this.createConnection();
  }

  private createConnection(): void {
    try {
      this.ws = new WebSocket(`${WS_BASE}/ws/scans/${this.scanId}`);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.onStatusChange(true);
      };

      this.ws.onmessage = (event) => {
        try {
          const update: ScanProgressUpdate = JSON.parse(event.data);
          this.onMessage(update);
        } catch {
          console.error('Failed to parse WebSocket message:', event.data);
        }
      };

      this.ws.onclose = () => {
        this.onStatusChange(false);
        if (!this.intentionallyClosed) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        this.onStatusChange(false);
      };
    } catch {
      this.onStatusChange(false);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.onConnectionFailed?.();
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      this.createConnection();
    }, Math.min(delay, 30000));
  }

  disconnect(): void {
    this.intentionallyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export function useScanUpdates(
  scanId: string,
  onMessage: MessageHandler,
  onStatusChange?: StatusHandler,
  onConnectionFailed?: ConnectionFailedHandler
): { connect: () => void; disconnect: () => void } {
  const ws = new ScanWebSocket(
    scanId,
    onMessage,
    onStatusChange || (() => {}),
    onConnectionFailed
  );

  return {
    connect: () => ws.connect(),
    disconnect: () => ws.disconnect(),
  };
}
