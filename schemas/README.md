# Runtime Observer schema

This folder contains the shared telemetry contract for Runtime Observer SDKs and collectors.

## Files

- `runtime_observer_schema.json` — JSON Schema draft 2020-12 event envelope and payload definitions.
- `examples/*.json` — one valid example per required MVP event kind.
- `tests/test_examples.py` — stdlib-only validation smoke tests for the schema/examples.

## Envelope rules

Every event uses the same envelope:

- `schema_version`: currently `1.0`.
- `event_id`: unique event UUID string.
- `timestamp`: UTC ISO-8601 timestamp.
- `service`: service metadata with `name`, `language`, `runtime_version`, and `sdk_version`.
- `trace_id`, `span_id`, `parent_span_id`: nullable correlation identifiers.
- `kind`: one of the required event kinds.
- `payload`: kind-specific payload validated by the schema definition matching `kind`.

## Span naming conventions

- Route span: `HTTP {method} {route_pattern}`
- DB span: `DB {operation} {table_or_unknown}`
- HTTP client span: `HTTP_CLIENT {method} {host}`
- LLM span: `LLM {provider} {model}`
- Log source: `{logger_name}` with route/trace correlation from active context

## Fingerprint conventions

- Route ID: stable hash of `service.name + method + route_pattern`.
- Exception fingerprint: hash of `exception.type + top_application_frame + normalized_message`.
- SQL fingerprint: normalized SQL with literals replaced by placeholders.

## Versioning

- Patch-compatible additions may add optional fields to payload definitions without changing `schema_version`.
- New required fields, renamed fields, removed fields, or changed semantics require a new minor schema version.
- SDKs should send the newest schema they support; collectors should reject unknown major versions with a useful error.
- Raw secrets, request bodies, LLM prompts, credentials, and unbounded object dumps are not allowed in examples or default SDK output.
