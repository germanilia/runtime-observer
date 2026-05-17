import { exportingEnabled } from './index.js';

export class BatchExporter {
  constructor(config, { browser = false } = {}) {
    this.config = config;
    this.browser = browser;
    this.queue = [];
    this.droppedEvents = 0;
    this.timer = null;
  }

  start() {
    if (this.timer || !exportingEnabled(this.config)) return;
    this.timer = setInterval(() => {
      this.flush().catch(() => undefined);
    }, this.config.flushIntervalMs || 2000);
    if (typeof this.timer.unref === 'function') this.timer.unref();
  }

  enqueue(event) {
    if (!exportingEnabled(this.config)) return;
    let candidate = event;
    try {
      if (new TextEncoder().encode(JSON.stringify(candidate)).length > this.config.maxEventSizeBytes) {
        candidate = { ...event, payload: { truncated: true, original_kind: event.kind } };
      }
    } catch {
      candidate = { ...event, payload: { truncated: true, original_kind: event.kind } };
    }
    if (this.queue.length >= this.config.maxQueueSize) {
      this.droppedEvents += 1;
      return;
    }
    this.queue.push(candidate);
  }

  async flush() {
    if (!exportingEnabled(this.config) || this.queue.length === 0) return;
    const events = this.queue.splice(0, this.config.batchSize || 100);
    try {
      await this.send(events);
    } catch {
      // Match the Python SDK's best-effort behavior. Keep bounded memory.
    }
  }

  async send(events) {
    const endpoint = String(this.config.endpoint || '').replace(/\/$/, '');
    const body = JSON.stringify({ batch_id: events[0]?.event_id, events });
    if (this.browser) {
      const url = `${endpoint}/v1/ingest/browser?api_key=${encodeURIComponent(this.config.apiKey || '')}`;
      // Do not use sendBeacon: it always attaches cookies for the target origin, which turns
      // ingest into a credentialed cross-origin request and trips Access-Control-Allow-Origin: *.
      // fetch with keepalive covers the page-unload case and lets us opt out of credentials.
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body,
        keepalive: true,
        credentials: 'omit',
        mode: 'cors',
      });
      if (!response.ok) throw new Error(`Runtime Observer ingest failed: ${response.status}`);
      return;
    }
    const response = await fetch(`${endpoint}/v1/ingest`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${this.config.apiKey || 'local-dev-key'}` },
      body,
    });
    if (!response.ok) throw new Error(`Runtime Observer ingest failed: ${response.status}`);
  }

  async shutdown() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    while (this.queue.length) await this.flush();
  }
}
