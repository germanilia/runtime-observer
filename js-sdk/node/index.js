import { AsyncLocalStorage } from 'node:async_hooks';
import { createRequire } from 'node:module';
import process from 'node:process';
import { performance } from 'node:perf_hooks';
import { BatchExporter } from '../core/exporter.js';
import { createEventBuilder, exceptionPayload, newId, normalizeConfig, safeUrl } from '../core/index.js';

const storage = new AsyncLocalStorage();

export function getCurrentContext() {
  return storage.getStore() || {};
}

export function withContext(context, fn) {
  return storage.run({ ...getCurrentContext(), ...context }, fn);
}

export class RuntimeObserver {
  constructor(options = {}) {
    this.config = normalizeConfig({ ...options, runtime: 'node' }, process.env);
    this.exporter = new BatchExporter(this.config);
    this.builder = createEventBuilder(this.config, { getContext: getCurrentContext, runtime: { version: process.version } });
    this.exporter.start();
    if (this.config.enabled) {
      this.emit('app_started', collectAppMetadata());
      this.emit('dependency_inventory', collectDependencyInventory());
    }
  }

  emit(kind, payload = {}, ids = {}) {
    const event = this.builder.event(kind, payload, ids);
    this.exporter.enqueue(event);
    return event;
  }

  emitEvent(kind, payload = {}, ids = {}) {
    return this.emit(kind, payload, ids);
  }

  async startSpan(name, fnOrOptions = {}, maybeOptions = {}) {
    const hasFn = typeof fnOrOptions === 'function';
    const fn = hasFn ? fnOrOptions : null;
    const options = hasFn ? maybeOptions : fnOrOptions;
    const parent = getCurrentContext();
    const spanId = newId();
    const traceId = parent.traceId || parent.trace_id || newId();
    const parentSpanId = parent.spanId || parent.span_id || null;
    const context = { ...parent, traceId, spanId, parentSpanId };
    const started = performance.now();
    this.emit('span_started', { name, kind: options.kind || 'custom', span_kind: options.kind || 'custom', attributes: options.attributes || {} }, { traceId, spanId, parentSpanId });
    if (!fn) return new ManualSpan(this, { name, kind: options.kind || 'custom', traceId, spanId, parentSpanId, started });
    return withContext(context, async () => {
      try {
        const result = await fn({ traceId, spanId, parentSpanId });
        this.emit('span_finished', { name, kind: options.kind || 'custom', span_kind: options.kind || 'custom', duration_ms: performance.now() - started, status: 'ok' }, { traceId, spanId, parentSpanId });
        return result;
      } catch (error) {
        this.captureException(error, options.extra || {}, { traceId, spanId, parentSpanId });
        this.emit('span_finished', { name, kind: options.kind || 'custom', span_kind: options.kind || 'custom', duration_ms: performance.now() - started, status: 'error', error_type: error?.name || 'Error' }, { traceId, spanId, parentSpanId });
        throw error;
      }
    });
  }

  captureException(error, extra = {}, ids = {}) {
    return this.emit('exception_raised', exceptionPayload(error, extra, this.config), ids);
  }

  instrumentFetch() {
    if (globalThis.fetch?._runtimeObserverWrapped) return true;
    const original = globalThis.fetch;
    if (typeof original !== 'function') return false;
    const observer = this;
    async function wrappedFetch(input, init = {}) {
      const started = performance.now();
      const method = String(init?.method || input?.method || 'GET').toUpperCase();
      const url = String(input?.url || input);
      let response;
      let error;
      try {
        response = await original(input, init);
        return response;
      } catch (exc) {
        error = exc;
        throw exc;
      } finally {
        observer.emit('http_client_call', { library: 'fetch', dependency_type: 'http', method, ...safeUrl(url), target: safeUrl(url).host, status_code: response?.status ?? null, duration_ms: performance.now() - started, error_type: error?.name || null });
      }
    }
    wrappedFetch._runtimeObserverWrapped = true;
    globalThis.fetch = wrappedFetch;
    this.emit('sdk_diagnostic', { instrumentation: 'fetch', status: 'instrumented' });
    return true;
  }

  instrumentExpress(app) {
    app.use(createExpressMiddleware(this));
    this.emit('sdk_diagnostic', { instrumentation: 'express', status: 'instrumented' });
  }

  instrumentConsole(levels = ['log', 'info', 'warn', 'error']) {
    for (const level of levels) {
      const original = console[level];
      if (typeof original !== 'function' || original._runtimeObserverWrapped) continue;
      const observer = this;
      console[level] = function runtimeObserverConsole(...args) {
        original.apply(console, args);
        const severity = level === 'log' ? 'INFO' : level.toUpperCase();
        observer.emit('log_record', { level: severity, logger_name: 'console', message: args.map((arg) => (typeof arg === 'string' ? arg : JSON.stringify(arg))).join(' ') });
      };
      console[level]._runtimeObserverWrapped = true;
    }
    this.emit('sdk_diagnostic', { instrumentation: 'console', status: 'instrumented' });
    return true;
  }

  emitDbQuery(payload = {}) {
    return this.emit('db_query', payload);
  }

  flush() {
    return this.exporter.flush();
  }

  shutdown() {
    return this.exporter.shutdown();
  }
}

class ManualSpan {
  constructor(observer, options) {
    this.observer = observer;
    this.options = options;
    this.ended = false;
  }

  end(extra = {}) {
    if (this.ended) return;
    this.ended = true;
    const { name, kind, traceId, spanId, parentSpanId, started } = this.options;
    this.observer.emit('span_finished', { name, kind, span_kind: kind, duration_ms: performance.now() - started, status: extra.status || 'ok', ...extra }, { traceId, spanId, parentSpanId });
  }
}

export function createExpressMiddleware(observer) {
  return function runtimeObserverExpress(req, res, next) {
    const method = req.method || 'GET';
    const routePattern = req.route?.path || req.path || req.url || '/';
    const traceId = req.get?.('x-runtime-observer-trace-id') || newId();
    const spanId = newId();
    const correlationId = req.get?.('x-correlation-id') || traceId;
    const started = performance.now();
    withContext({ traceId, spanId, correlationId, method, routePattern, path: req.path || req.url }, () => {
      observer.emit('request_started', { request_id: spanId, method, path: req.path || req.url, route_pattern: routePattern, correlation_id: correlationId }, { traceId, spanId });
      observer.emit('span_started', { name: `HTTP ${method} ${routePattern}`, kind: 'route', span_kind: 'route', method, route_pattern: routePattern }, { traceId, spanId });
      res.on('finish', () => {
        const finalPattern = req.route?.path || routePattern;
        const duration = performance.now() - started;
        observer.emit('request_finished', { request_id: spanId, method, path: req.path || req.url, route_pattern: finalPattern, status_code: res.statusCode, duration_ms: duration, correlation_id: correlationId }, { traceId, spanId });
        observer.emit('span_finished', { name: `HTTP ${method} ${finalPattern}`, kind: 'route', span_kind: 'route', duration_ms: duration, status: res.statusCode >= 500 ? 'error' : 'ok' }, { traceId, spanId });
      });
      next();
    });
  };
}

export function initRuntimeObserver(options = {}) {
  return new RuntimeObserver(options);
}

initRuntimeObserver.fromEnv = (overrides = {}) => new RuntimeObserver(overrides);

function collectAppMetadata() {
  return { started_at: new Date().toISOString(), environment: process.env.NODE_ENV || 'development', pid: process.pid, argv: process.argv.slice(0, 5), platform: process.platform, node_version: process.version };
}

function collectDependencyInventory() {
  try {
    const require = createRequire(import.meta.url);
    const pkg = require(`${process.cwd()}/package.json`);
    const dependencies = Object.entries({ ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) }).map(([name, version]) => ({ name, version }));
    return { package_name: pkg.name, package_version: pkg.version, dependencies };
  } catch {
    return { dependencies: [] };
  }
}

export { exceptionPayload, newId, safeUrl } from '../core/index.js';
