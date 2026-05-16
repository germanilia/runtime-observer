import { performance } from '../browser/performance.js';
import { BatchExporter } from '../core/exporter.js';
import { createEventBuilder, exceptionPayload, newId, normalizeConfig, safeUrl } from '../core/index.js';

let currentContext = {};

export function getCurrentContext() {
  return currentContext;
}

export function withContext(context, fn) {
  const previous = currentContext;
  currentContext = { ...previous, ...context };
  try {
    return fn();
  } finally {
    currentContext = previous;
  }
}

export class BrowserObserver {
  constructor(options = {}) {
    this.config = normalizeConfig({ projectName: 'browser', serviceName: 'frontend', ...options, runtime: 'browser' }, {});
    this.exporter = new BatchExporter(this.config, { browser: true });
    this.builder = createEventBuilder(this.config, { getContext: getCurrentContext, runtime: { version: globalThis.navigator?.userAgent || 'browser' } });
    this.exporter.start();
  }

  emit(kind, payload = {}, ids = {}) {
    const event = this.builder.event(kind, payload, ids);
    this.exporter.enqueue(event);
    return event;
  }

  emitEvent(kind, payload = {}, ids = {}) {
    return this.emit(kind, payload, ids);
  }

  captureException(error, extra = {}, ids = {}) {
    return this.emit('exception_raised', exceptionPayload(error, extra, this.config), ids);
  }

  installBrowserHooks() {
    globalThis.addEventListener?.('error', (event) => {
      this.emit('log_record', { level: 'ERROR', logger_name: 'browser.error', message: event.message, source_file: event.filename, source_line: event.lineno, exception: exceptionPayload(event.error || event.message, {}, this.config) });
    });
    globalThis.addEventListener?.('unhandledrejection', (event) => {
      this.emit('log_record', { level: 'ERROR', logger_name: 'browser.unhandledrejection', message: String(event.reason?.message || event.reason || 'Unhandled promise rejection'), exception: exceptionPayload(event.reason, {}, this.config) });
    });
    globalThis.addEventListener?.('pagehide', () => {
      this.flush().catch(() => undefined);
    });
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
    this.emit('sdk_diagnostic', { instrumentation: 'browser.fetch', status: 'instrumented' });
    return true;
  }

  captureNavigation() {
    this.emit('log_record', { level: 'INFO', logger_name: 'browser.navigation', message: 'page viewed', location: globalThis.location?.href, path: globalThis.location?.pathname });
  }

  instrumentConsole(levels = ['error', 'warn']) {
    for (const level of levels) {
      const original = globalThis.console?.[level];
      if (typeof original !== 'function' || original._runtimeObserverWrapped) continue;
      const observer = this;
      globalThis.console[level] = function runtimeObserverConsole(...args) {
        original.apply(globalThis.console, args);
        observer.emit('log_record', { level: level.toUpperCase(), logger_name: 'browser.console', message: args.map((arg) => (typeof arg === 'string' ? arg : JSON.stringify(arg))).join(' ') });
      };
      globalThis.console[level]._runtimeObserverWrapped = true;
    }
    this.emit('sdk_diagnostic', { instrumentation: 'browser.console', status: 'instrumented' });
    return true;
  }

  async flush() {
    await this.exporter.flush();
  }

  async shutdown() {
    await this.exporter.shutdown();
  }
}

export function initBrowserObserver(options = {}) {
  return new BrowserObserver(options);
}

export function configureRuntimeObserver(options = {}) {
  defaultObserver = new BrowserObserver(options);
  return defaultObserver;
}

export function emitRuntimeObserverEvent(kind, payload = {}, context = {}) {
  if (!defaultObserver) defaultObserver = new BrowserObserver();
  defaultObserver.emit(kind, payload, context);
  return defaultObserver.flush().then(() => ({ accepted: true }));
}

export function installRuntimeObserverBrowserHooks() {
  if (!defaultObserver) defaultObserver = new BrowserObserver();
  defaultObserver.installBrowserHooks();
}

let defaultObserver;

export { exceptionPayload, newId, safeUrl } from '../core/index.js';
