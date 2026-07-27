Status: ready-for-agent

# 03 — `entity_filter` round-trips through the shareable URL

## Parent

[`PRD.md`](PRD.md)

## What to build

Extend `app/spec_url.py`'s `encode_spec`/`decode_spec` to carry `entity_filter`, following the
exact existing pattern used for `chart_metric`: present in the encoded query params only when
non-`None`, decoded back through `ReportSpec`'s own validator (so a hand-edited or stale link
still gets the same normalization/error handling every other field gets).

This file's own docstring notes that fields are enumerated from `ReportSpec.model_fields`
specifically so an added field that isn't taught to the encoder fails a test rather than shipping
a link that silently drops it — the existing round-trip test in `tests/test_spec_url.py` should
already catch a missed field once `entity_filter` exists on the model; extend it explicitly to
assert the filter's value (both set and absent) survives the round trip.

## Acceptance criteria

- [ ] A `ReportSpec` with `entity_filter` set to a real value encodes to a query param and decodes
      back to the identical value
- [ ] A `ReportSpec` with `entity_filter == None` omits the param entirely (not an empty-string
      param)
- [ ] The existing round-trip test is extended to cover both cases, same style as the existing
      `chart_metric` coverage
- [ ] `make check` passes

## Blocked by

- [02 — `entity_filter` on ReportSpec + engine filtering](02-entity-filter-engine.md)
