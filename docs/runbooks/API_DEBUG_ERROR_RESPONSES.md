# Runbook: API Error Responses and `DEBUG` in a Live Incident

**Status:** Active
**Last Updated:** 2026-08-29
**Applies to:** `src/api/main.py`, `src/api/security_middleware.py` (`SecureExceptionMiddleware`)
**Related control:** `AURA-CTL-003` in `docs/security/CONTROL_REGISTRY.md`

---

## Symptom: "I set `DEBUG=true` and the 500 response looks exactly the same"

This is expected behaviour outside dev and test, and it is the reason this runbook exists.

`SecureExceptionMiddleware` honors a debug request **only** when the resolved environment is one of
`dev`, `development`, `local`, `test` (`DEBUG_SAFE_ENVIRONMENTS`, `src/api/security_middleware.py:34`).
Anywhere else it discards the flag, logs one error, and serves the generic body. Setting `DEBUG=true`
on a `prod`, `qa` or `staging` deployment changes nothing in the response.

**Separately, and in every environment including dev: the exception message is never in the response.**
Debug mode adds the exception *type name* and a pointer to the log. `str(e)` was removed because it
routinely carries connection strings, ARNs, account identifiers and fragments of the request body.

**You have not lost the detail.** `logger.exception` records the message and the full traceback
server-side, against the same `request_id` the caller receives. The procedure below is how you get it.

---

## What to do instead

### 1. Take the `request_id` from the failing response

Every error response carries it, and it is also on the `X-Request-ID` response header.

```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred. Please try again later.",
  "request_id": "6f1e9c3a-2d47-4a10-9b8e-77c0d1a4f5b2"
}
```

If you are driving the request yourself, **set your own correlation ID** rather than fishing one out
of the response. `RequestIDMiddleware` accepts an inbound `X-Request-ID` and reuses it verbatim:

```bash
curl -i -H "X-Request-ID: incident-4821-repro-1" https://<host>/<failing-path>
```

### 2. Find the record in the server log

The exception message and traceback are logged by `SecureExceptionMiddleware.dispatch` in the form:

```text
Unhandled exception: <ExceptionType>: <message> request_id=<id> path=<path>
```

followed by the traceback. Search the service log for the `request_id`. `RequestIDMiddleware` also
emits a completion line for the same ID (method, path, status, duration), so the request is
reconstructable end to end from that one string.

### 3. Do not set `DEBUG=true` in production to get more

It will not produce more. The most it ever adds, and only in a debug-safe environment, is the
exception type name -- which the log line above already gives you, alongside everything else.

---

## Response shapes

**Debug not requested, or requested and refused** -- all environments:

```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred. Please try again later.",
  "request_id": "<uuid>"
}
```

**Debug requested and honored** -- `DEBUG=true` with `ENVIRONMENT` in `DEBUG_SAFE_ENVIRONMENTS`:

```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred. Please try again later.",
  "request_id": "<uuid>",
  "debug": {
    "exception": "ValueError",
    "detail": "Exception message and traceback are in the server log; correlate using request_id."
  }
}
```

`request_id` is present whenever `include_request_id` is true, which is what `add_security_middleware`
passes. There is no configuration that puts the exception message on the wire.

---

## Diagnosing a refusal

The refusal is logged **once at application startup**, when the middleware is constructed -- not on
each 500. If you enabled `DEBUG` and restarted, look at the startup log, not at the log around the
failing request:

```text
Debug error responses requested but refused: environment=prod is not one of
['dev', 'development', 'local', 'test']. Exception details stay server-side.
```

Emitted at `ERROR` by `src.api.security_middleware`. If you see this line, `DEBUG` was read as true
and deliberately dropped. If you see no such line and still get no `debug` block, `DEBUG` was not
true in the process environment -- check that it reached the container, not just the shell.

---

## How the environment is resolved

`ENVIRONMENT` is normalized once, at `main.py:395`, and every environment-dependent decision
derives from that single value. Two derived forms exist, and they default differently on purpose.

| # | Site | Value when `ENVIRONMENT` is unset or blank | Governs |
|---|---|---|---|
| 1 | `main.py:395` (`_environment_configured`) | `None` | Canonical. Passed to the middleware at `main.py:481` |
| 2 | `main.py:401` (`_environment`) | `dev`, with a `WARNING` at `main.py:454` | `/docs`, `/redoc`, `/openapi.json`; the CORS empty-origin refusal; HSTS |
| 3 | `security_middleware.py:284` | `prod` | The debug interlock, when no `environment` argument is given |

Normalization is `.strip().lower()`, and a value that is empty after stripping is treated as unset.
Case and surrounding whitespace therefore cannot make two decisions disagree.

**Why two defaults rather than one.** `dev` is the right default for HSTS and the docs gate --
forcing HSTS on a developer laptop breaks local HTTP browsing. It is the wrong default for
returning exception detail. So `main.py` passes the *raw* resolution (`None` when unset) to the
middleware rather than its own `dev` fallback, which lets resolution 3 apply.

**Consequence: with `ENVIRONMENT` unset, `DEBUG=true` is refused.** The middleware resolves `prod`
and withholds the debug block. `/docs` stays reachable and HSTS stays off, because those read
resolution 2.

**Set `ENVIRONMENT` explicitly in every deployed environment** regardless. It is listed as required
in `docs/deployment/DEPLOYMENT_GUIDE.md`, and the warning at `main.py:454` is the only signal that
it is missing.

### Previous behavior, for anyone reading older notes

Until `main.py` was corrected, it passed its own `dev` fallback to the middleware. On the assembled
application an unset `ENVIRONMENT` therefore resolved to `dev` and `DEBUG=true` **was** honored;
the middleware's `prod` default was unreachable through `main.py` and protected only a direct
consumer that passed no environment. Exposure in that state was bounded to the exception *type
name*, since the message and traceback are withheld unconditionally.

Two edge cases went with it, both now resolved by normalizing once:

- **Case.** `ENVIRONMENT=DEV` was `dev` to the debug interlock but not-`dev` to the HSTS check, so
  HSTS switched on while debug stayed enabled.
- **Empty string.** `ENVIRONMENT=""` is not `None`, so it slipped past the unset check without
  warning and produced a different answer at each of the three sites.

A third case was found while fixing this and is worth recording: a padded value such as
`ENVIRONMENT="  prod  "` did not match `("prod", "production")`, so the **CORS empty-origin refusal
was skipped in production**. Normalization closes that too.

`tests/test_security_middleware.py::test_main_wires_debug_interlock` pins the wiring across all of
these cases by importing `main.py` under each environment and resolving the real middleware.

---

## Enabling debug output legitimately

In a dev, local or test environment:

```bash
export ENVIRONMENT=dev     # or development, local, test
export DEBUG=true
```

Both are required. `DEBUG=true` alone does nothing unless `ENVIRONMENT` is debug-safe, and
`ENVIRONMENT=dev` alone does nothing unless `DEBUG` is true.

---

## Related

- `docs/security/CONTROL_REGISTRY.md` -- `AURA-CTL-003`, the control this behaviour implements
- `docs/deployment/DEPLOYMENT_GUIDE.md` -- Application Environment Variables
- `docs/standards/LOGGING_STANDARDS.md` -- log levels; note that the `DEBUG` variable here is an
  error-response flag, unrelated to the `DEBUG` *log level*
- `tests/test_security_middleware.py` -- `TestSecureExceptionHandler` covers the refusal, the
  unset-environment path, case insensitivity, and that `str(e)` never reaches the body
