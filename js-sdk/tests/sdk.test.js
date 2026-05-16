import test from 'node:test';
import assert from 'node:assert/strict';
import { redactMapping, createEventBuilder, normalizeConfig } from '../core/index.js';
import { initRuntimeObserver, withContext, getCurrentContext } from '../node/index.js';

test('redacts obvious secrets', () => {
  const value = redactMapping({ authorization: 'Bearer abcdefghijklmnopqrstuvwxyz', nested: { token: 'secret' } });
  assert.equal(value.authorization, '<redacted>');
  assert.equal(value.nested.token, '<redacted>');
});

test('builds schema-compatible events', () => {
  const config = normalizeConfig({ projectName: 'checkout', serviceName: 'api' });
  const builder = createEventBuilder(config, { getContext: () => ({ traceId: 't1' }) });
  const event = builder.event('log_record', { level: 'INFO', message: 'ok' });
  assert.equal(event.schema_version, '1.0');
  assert.equal(event.kind, 'log_record');
  assert.equal(event.trace_id, 't1');
  assert.equal(event.service.name, 'api');
});

test('node observer preserves async context', async () => {
  const observer = initRuntimeObserver({ projectName: 'checkout', apiKey: 'key', serviceName: 'api', endpoint: 'http://127.0.0.1:9' });
  await withContext({ traceId: 'trace-1' }, async () => {
    assert.equal(getCurrentContext().traceId, 'trace-1');
    observer.emit('log_record', { level: 'INFO', message: 'hello' });
  });
  await observer.shutdown();
});
