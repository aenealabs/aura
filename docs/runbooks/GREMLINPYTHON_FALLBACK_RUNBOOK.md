# gremlinpython Fallback Runbook

**Last Updated:** 2026-05-08
**Tracked As:** At-Risk in `docs/security/DEPENDENCY_RISK_REGISTER.md`
**Owner:** Platform Engineering

---

## Why this runbook exists

`gremlinpython` (the Python binding for Apache TinkerPop) is the SDK we use to talk to AWS Neptune via the Gremlin protocol. It is on the At-Risk tier of the dependency register because the Python binding has historically had thinner maintenance than the Java reference implementation. The TinkerPop project itself (Apache) is healthy; the risk is that the Python binding could lag behind on Python compatibility, security fixes, or Neptune-specific features.

This runbook is the documented contingency for "if Python binding maintenance slows further, what do we do". The plan is to swap the binding for direct HTTP calls against Neptune's REST endpoint -- already supported by Neptune, no Neptune-side changes needed.

## Trigger conditions for executing the swap

Execute the swap only if at least one of:

1. **Python compatibility lag**: `gremlinpython` does not support a Python version we need to deploy on (e.g., Python 3.13+) within 6 months of that version's GA.
2. **Unpatched CVE**: a CVE in `gremlinpython` lacks a fix release within 30 days of disclosure.
3. **Project EOL**: TinkerPop or the Python binding maintainers explicitly announce end-of-life.

The recurring dependency audit (`.github/workflows/dependency-risk-audit.yml`) is the primary detection mechanism; the audit posts staleness signals to tracking issue #138.

Until then: **track, don't swap**. A speculative HTTP transport rewrite costs engineering time we don't have a forcing function to spend.

## Structural readiness already in place

The `nest-asyncio` replacement (commit `2feb44c`) introduced `_ThreadDispatchedGremlinClient` in `src/services/neptune_graph_service.py`. That wrapper is the abstraction seam: it exposes a `submit(q).all().result()` surface and dispatches to the underlying client. Today the underlying client is `gremlin_python.driver.client.Client`. To swap, replace the underlying client with an HTTP-backed implementation that exposes the same surface.

Three files import `gremlin_python` directly today:

| File | Usage shape |
| --- | --- |
| `src/services/neptune_graph_service.py` | `client.Client(...)`, `submit(q).all().result()` -- already wrapped |
| `src/services/supply_chain/graph_integration.py` | `client.Client(...)`, `submit(q).all().result()` |
| `src/migration/neptune_to_neo4j.py` | `client.Client(...)` -- migration tool, separate concern |

The supply-chain service should also be brought behind the same wrapper before the swap; the migration tool is one-shot and can stay as-is.

## Neptune HTTP API surface

Neptune supports Gremlin queries directly via HTTP:

```
POST https://<cluster-endpoint>:8182/gremlin
Authorization: <SigV4 from boto3/botocore>
Content-Type: application/json

{"gremlin": "g.V().limit(1)"}
```

Response:

```json
{
  "requestId": "...",
  "status": {"code": 200, "message": "", "attributes": {}},
  "result": {"data": [...], "meta": {}}
}
```

The result shape is the same as what `gremlin-python`'s `.result()` returns -- a list of vertex/edge/scalar payloads -- so the HTTP-backed wrapper can match the existing call sites without changes.

## Swap implementation sketch

When trigger conditions are met, the swap is roughly:

1. **Build an HTTP-backed client** in `src/services/neptune_graph_service.py`:

   ```python
   class _NeptuneHttpClient:
       def __init__(self, endpoint: str, port: int, region: str, ...):
           self._endpoint = endpoint
           self._port = port
           self._session = boto3.Session()
           self._signer = botocore.auth.SigV4Auth(
               self._session.get_credentials(), "neptune-db", region
           )

       def submit(self, query: str) -> "_HttpSubmitResult":
           return _HttpSubmitResult(self, query)

       def _post(self, query: str) -> list:
           url = f"https://{self._endpoint}:{self._port}/gremlin"
           body = json.dumps({"gremlin": query})
           req = botocore.awsrequest.AWSRequest(
               method="POST", url=url,
               data=body,
               headers={"Content-Type": "application/json"},
           )
           self._signer.add_auth(req)
           # Use httpx (already a project dep) for the actual call.
           resp = httpx.post(url, content=body, headers=dict(req.headers), timeout=30)
           resp.raise_for_status()
           return resp.json()["result"]["data"]

       def close(self) -> None:
           pass  # httpx is request-scoped
   ```

2. **Plug it into the existing wrapper** by switching `_init_aws_mode` to construct `_NeptuneHttpClient` instead of `gremlin_python.driver.client.Client`. The `_ThreadDispatchedGremlinClient` shim continues to work since the surface is the same.

3. **Drop the gremlinpython pin** from `requirements.txt` and `requirements-api.txt`.

4. **Update the register's "Replacement Decisions Made" table** with date, rationale, and a link to the swap commit.

5. **Update `src/migration/neptune_to_neo4j.py`** to use the same HTTP path, or keep it on gremlinpython if gremlinpython is still installable and it's a one-shot tool.

## What this runbook is not

- A justification for swapping today. We have no trigger; the Python binding works.
- A complete reference for the HTTP API. Neptune's documentation is the source of truth for edge cases (large result paging, error response shapes, etc.).
- A blueprint for moving off Neptune entirely. That would be a much larger project (data model, query language, transactions) and is out of scope here.

## References

- Register entry: `docs/security/DEPENDENCY_RISK_REGISTER.md` -- gremlinpython row
- The wrapper that sets the swap seam: `src/services/neptune_graph_service.py`, `_ThreadDispatchedGremlinClient`
- Wrapper tests: `tests/test_gremlin_thread_dispatch.py`
- Neptune HTTP endpoint docs: AWS Neptune User Guide, "Gremlin HTTP REST API"
- Tracking issue for ongoing audit signal: #138
