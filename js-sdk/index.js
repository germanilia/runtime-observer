let config = {
  endpoint: 'http://127.0.0.1:4319',
  apiKey: '',
  projectName: 'browser',
  serviceName: 'frontend',
  displayName: '',
  enabled: true,
};

function nowIso() {
  return new Date().toISOString();
}

function eventId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `browser-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function service() {
  return {
    project_name: config.projectName,
    name: config.serviceName,
    display_name: config.displayName || config.serviceName,
    language: 'javascript',
    runtime_version: globalThis.navigator?.userAgent || 'browser',
    sdk_version: '0.1.0',
  };
}

export function configureRuntimeObserver(options = {}) {
  config = { ...config, ...options };
}

export async function emitRuntimeObserverEvent(kind, payload = {}, context = {}) {
  if (!config.enabled) return { skipped: true };
  const endpoint = String(config.endpoint || '').replace(/\/$/, '');
  const isBrowser = typeof globalThis.window !== 'undefined' && typeof globalThis.document !== 'undefined';
  const url = isBrowser ? `${endpoint}/v1/ingest/browser?api_key=${encodeURIComponent(config.apiKey || '')}` : `${endpoint}/v1/ingest`;
  const event = {
    schema_version: '1.0',
    event_id: eventId(),
    timestamp: nowIso(),
    service: service(),
    kind,
    trace_id: context.traceId,
    span_id: context.spanId,
    parent_span_id: context.parentSpanId,
    payload,
  };
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      ...(isBrowser ? {} : { authorization: `Bearer ${config.apiKey || ''}` }),
    },
    body: JSON.stringify({ events: [event] }),
    keepalive: true,
  });
  if (!response.ok) throw new Error(`Runtime Observer ingest failed: ${response.status}`);
  return response.json();
}

export function installRuntimeObserverBrowserHooks() {
  globalThis.addEventListener?.('error', (event) => {
    emitRuntimeObserverEvent('log_record', {
      level: 'ERROR',
      logger_name: 'browser.error',
      message: event.message,
      source_file: event.filename,
      source_line: event.lineno,
      exception: { message: event.message, stack: event.error?.stack },
    }).catch(() => undefined);
  });
  globalThis.addEventListener?.('unhandledrejection', (event) => {
    emitRuntimeObserverEvent('log_record', {
      level: 'ERROR',
      logger_name: 'browser.unhandledrejection',
      message: String(event.reason?.message || event.reason || 'Unhandled promise rejection'),
      exception: { stack: event.reason?.stack },
    }).catch(() => undefined);
  });
}
