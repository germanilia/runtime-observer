export const SCHEMA_VERSION = '1.0';
export const SDK_VERSION = '0.2.0';

export const VALID_EVENT_KINDS = new Set([
  'app_started',
  'dependency_inventory',
  'route_discovered',
  'request_started',
  'request_finished',
  'span_started',
  'span_finished',
  'exception_raised',
  'db_query',
  'http_client_call',
  'llm_call',
  'log_record',
  'metric_counter',
  'sdk_diagnostic',
  'function_called',
  'function_returned',
  'background_job_started',
  'background_job_finished',
  'tool_call',
]);

const SECRET_KEY_RE = /password|passwd|secret|token|api[_-]?key|apikey|authorization|cookie|set-cookie|credential|private[_-]?key|access[_-]?key|refresh[_-]?token|id[_-]?token/i;
const JWT_RE = /eyJ[A-Za-z0-9_-]{2,}\.[A-Za-z0-9_-]{2,}\.[A-Za-z0-9_-]{2,}/g;
const AWS_KEY_RE = /\b(AKIA|ASIA)[A-Z0-9]{16}\b/g;
const BEARER_RE = /Bearer\s+[A-Za-z0-9._~+/=-]{12,}/gi;
const PEM_RE = /-----BEGIN [^-]+-----[\s\S]*?-----END [^-]+-----/g;
const LONG_B64_RE = /\b[A-Za-z0-9+/]{40,}={0,2}\b/g;
const KEY_VALUE_SECRET_RE = /\b(password|passwd|secret|token|api[_-]?key|apikey|authorization|cookie|credential|private[_-]?key|access[_-]?key|refresh[_-]?token|id[_-]?token)\s*[:=]\s*([^\s,;]+)/gi;

export function nowIso() {
  return new Date().toISOString();
}

export function newId(prefix = 'ro') {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function stableHash(value) {
  const text = String(value);
  if (globalThis.crypto?.subtle) {
    const bytes = new TextEncoder().encode(text);
    const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
    return `sha256:${Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('').slice(0, 16)}`;
  }
  let hash = 0;
  for (let index = 0; index < text.length; index += 1) hash = ((hash << 5) - hash + text.charCodeAt(index)) | 0;
  return `hash:${Math.abs(hash).toString(16)}`;
}

function entropy(value) {
  if (!value) return 0;
  const counts = new Map();
  for (const char of value) counts.set(char, (counts.get(char) || 0) + 1);
  let result = 0;
  for (const count of counts.values()) {
    const p = count / value.length;
    result -= p * Math.log2(p);
  }
  return result;
}

export function redactString(value, { maxStringLength = 512 } = {}) {
  let redacted = String(value)
    .replace(PEM_RE, '<redacted:pem>')
    .replace(BEARER_RE, 'Bearer <redacted:token>')
    .replace(JWT_RE, '<redacted:jwt>')
    .replace(AWS_KEY_RE, '<redacted:aws_access_key>')
    .replace(LONG_B64_RE, (match) => (entropy(match) > 4 ? '<redacted:high_entropy>' : match))
    .replace(KEY_VALUE_SECRET_RE, (_, key) => `${key}=<redacted>`);
  if (redacted.length > maxStringLength) redacted = `${redacted.slice(0, maxStringLength)}…<truncated>`;
  return redacted;
}

export function redactValue(value, key, options = {}, depth = 0) {
  const { maxStringLength = 512, maxDepth = 3, maxObjectKeys = 25 } = options;
  if (key && SECRET_KEY_RE.test(String(key))) return '<redacted>';
  if (value == null || typeof value === 'boolean' || typeof value === 'number') return value;
  if (typeof value === 'string') return redactString(value, { maxStringLength });
  if (depth >= maxDepth) return '<max-depth>';
  if (Array.isArray(value)) return value.slice(0, maxObjectKeys).map((item) => redactValue(item, undefined, options, depth + 1));
  if (typeof value === 'object') {
    const output = {};
    for (const [childKey, childValue] of Object.entries(value).slice(0, maxObjectKeys)) {
      output[redactString(childKey, { maxStringLength: 64 })] = redactValue(childValue, childKey, options, depth + 1);
    }
    return output;
  }
  return redactString(String(value), { maxStringLength });
}

export function redactMapping(value, options = {}) {
  return redactValue(value || {}, undefined, options);
}

export function normalizeConfig(options = {}, env = {}) {
  const captureMode = String(options.captureMode ?? env.RUNTIME_OBSERVER_CAPTURE_MODE ?? 'dev').toLowerCase();
  const mode = ['dev', 'prod', 'off'].includes(captureMode) ? captureMode : 'dev';
  const projectName = options.projectName ?? env.RUNTIME_OBSERVER_PROJECT_NAME ?? '';
  const serviceName = options.serviceName ?? env.RUNTIME_OBSERVER_SERVICE_NAME ?? 'javascript-service';
  return {
    endpoint: options.endpoint ?? env.RUNTIME_OBSERVER_ENDPOINT ?? 'http://127.0.0.1:4319',
    apiKey: options.apiKey ?? env.RUNTIME_OBSERVER_API_KEY ?? '',
    projectName,
    serviceName,
    displayName: options.displayName ?? env.RUNTIME_OBSERVER_DISPLAY_NAME ?? '',
    environment: options.environment ?? env.RUNTIME_OBSERVER_ENVIRONMENT ?? (mode === 'prod' ? 'production' : 'development'),
    enabled: parseBool(options.enabled ?? env.RUNTIME_OBSERVER_ENABLED, true),
    captureMode: mode,
    batchSize: parseIntValue(options.batchSize ?? env.RUNTIME_OBSERVER_BATCH_SIZE, 100),
    flushIntervalMs: parseFloatValue(options.flushIntervalMs ?? env.RUNTIME_OBSERVER_FLUSH_INTERVAL_MS, parseFloatValue(env.RUNTIME_OBSERVER_FLUSH_INTERVAL_SECONDS, 2) * 1000),
    maxQueueSize: parseIntValue(options.maxQueueSize ?? env.RUNTIME_OBSERVER_MAX_QUEUE_SIZE, 1000),
    maxEventSizeBytes: parseIntValue(options.maxEventSizeBytes ?? env.RUNTIME_OBSERVER_MAX_EVENT_SIZE_BYTES, 64 * 1024),
    maxStringLength: parseIntValue(options.maxStringLength ?? env.RUNTIME_OBSERVER_MAX_STRING_LENGTH, 512),
    maxDepth: parseIntValue(options.maxDepth ?? env.RUNTIME_OBSERVER_MAX_PARAMETER_DEPTH, 3),
    maxObjectKeys: parseIntValue(options.maxObjectKeys ?? env.RUNTIME_OBSERVER_MAX_OBJECT_KEYS, 25),
    captureDbQueryValues: parseBool(options.captureDbQueryValues ?? env.RUNTIME_OBSERVER_CAPTURE_DB_QUERY_VALUES, mode !== 'prod'),
    insecureLocalDev: parseBool(options.insecureLocalDev ?? env.RUNTIME_OBSERVER_INSECURE_LOCAL_DEV, false),
    runtime: options.runtime ?? 'javascript',
  };
}

function parseBool(value, fallback) {
  if (value == null || value === '') return fallback;
  if (typeof value === 'boolean') return value;
  return ['1', 'true', 'yes', 'on'].includes(String(value).toLowerCase());
}

function parseIntValue(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ''), 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseFloatValue(value, fallback) {
  const parsed = Number.parseFloat(String(value ?? ''));
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function exportingEnabled(config) {
  return Boolean(config.enabled && config.captureMode !== 'off' && config.projectName && (config.apiKey || config.insecureLocalDev));
}

export function createService(config, runtime = {}) {
  const service = {
    project_name: config.projectName || '',
    name: config.serviceName || 'javascript-service',
    language: 'javascript',
    runtime_version: runtime.version || globalThis.navigator?.userAgent || 'unknown',
    sdk_version: SDK_VERSION,
    environment: config.environment,
  };
  if (config.displayName) service.display_name = config.displayName;
  return service;
}

export function createEventBuilder(config, { getContext = () => ({}), runtime = {} } = {}) {
  return {
    event(kind, payload = {}, ids = {}) {
      if (!VALID_EVENT_KINDS.has(kind)) throw new Error(`unsupported event kind: ${kind}`);
      const context = getContext() || {};
      return {
        schema_version: SCHEMA_VERSION,
        event_id: newId(),
        timestamp: nowIso(),
        service: createService(config, runtime),
        trace_id: ids.traceId ?? ids.trace_id ?? context.traceId ?? context.trace_id ?? null,
        span_id: ids.spanId ?? ids.span_id ?? context.spanId ?? context.span_id ?? null,
        parent_span_id: ids.parentSpanId ?? ids.parent_span_id ?? context.parentSpanId ?? context.parent_span_id ?? null,
        kind,
        payload: redactMapping(payload, config),
      };
    },
  };
}

export function exceptionPayload(error, extra = {}, config = {}) {
  const err = error instanceof Error ? error : new Error(String(error));
  return redactMapping({
    type: err.name || 'Error',
    message: err.message || String(error),
    stack: String(err.stack || ''),
    cause: err.cause ? { type: err.cause.name || 'Error', message: err.cause.message || String(err.cause) } : undefined,
    fingerprint: `${err.name || 'Error'}:${String(err.message || '').slice(0, 120)}`,
    ...extra,
  }, config);
}

export function safeUrl(url) {
  try {
    const parsed = new URL(String(url));
    const query = parsed.search ? '?<redacted>' : '';
    return { scheme: parsed.protocol.replace(':', ''), host: parsed.host, path: parsed.pathname || '/', url: `${parsed.protocol}//${parsed.host}${parsed.pathname || '/'}${query}` };
  } catch {
    return { scheme: null, host: null, path: null, url: redactString(String(url)) };
  }
}
