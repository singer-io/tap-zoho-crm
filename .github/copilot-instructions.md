# Instructions for Building a Singer Tap/Target  
*Following Singer.io Best Practices*

This document provides guidance for implementing a high-quality Singer Tap (or Target) in compliance with the Singer specification and community best practices. Use it in conjunction with GitHub Copilot or your preferred IDE.

---

## 1. Rate Limiting  
- Respect API rate limits (e.g., daily quotas or per-second limits).  
- For short-term rate limits, detect HTTP 429 or similar errors and implement retries with sleep/delay. Use Singer’s built-in rate-limiting utilities where available.  
:contentReference[oaicite:1]{index=1}

## 2. Memory Efficiency  
- Minimize RAM usage by streaming data—for example, use generators or iterators rather than loading entire datasets.  
:contentReference[oaicite:2]{index=2}

## 3. Consistent Date Handling  
- Use **RFC 3339** format (including time zone offset). UTC (`Z`) is preferred. Examples:  
  - Good: `2017-01-01T00:00:00Z`, `2017-01-01T00:00:00-05:00`  
  - Bad: `2017-01-01 00:00:00`  
- Use `pytz` for timezone-aware conversions for accuracy.  
:contentReference[oaicite:3]{index=3}

## 4. Logging & Exception Handling  
- Log every API request (URL + parameters), omitting sensitive info (e.g., API keys).  
- Log progress (e.g., “Starting stream X”).  
- On API errors, log the status code and response body.  
- For fatal errors, log at `CRITICAL` or `FATAL` level and exit with non-zero status. Omit stack trace for known, user-triggered error conditions; include full trace for unknown exceptions.  
- For recoverable errors, implement retries with exponential backoff (e.g., using the `backoff` library).  
:contentReference[oaicite:4]{index=4}

### 📁 JSON Schema Guidelines

- All files under `schema/*.json` must follow the [JSON Schema standard](https://json-schema.org/).
- Any fields named `created_time`, `modified_time`, or ending in `_time` **must use the `date-time` format**.
  
  ✅ Example:
  ```json
  {
    "type": "object",
    "properties": {
      "created_time": {
        "type": ["null", "string"],
        "format": "date-time"
      },
      "last_access_time": {
        "type": ["null", "string"],
        "format": "date-time"
      }
    }
  }

## 5. Module Structure  
- Organize code in a proper module (folder) with `__init__.py`, not a single script file.  
:contentReference[oaicite:5]{index=5}

## 6. Schema Management  
- For static schemas, store them as `.json` files in a `schemas/` directory—not as code-defined dicts.  
- Prefer explicit schemas: avoid `additionalProperties: true` or vague typing. Use explicit field names and types, and set `additionalProperties: false` when the schema should be strict.  
- Be cautious when tightening schemas in new releases—this may require a major version bump per semantic versioning.  
:contentReference[oaicite:6]{index=6}

## 7. Code Quality  
- Use `pylint` and aim for zero error-level messages.  
- Assume that CI (e.g., CircleCI) will enforce linting. Fix or explicitly disable messages as needed.  
:contentReference[oaicite:7]{index=7}

## 8. Dependency Versioning  
- Pin all dependencies to specific versions.  
  ```python
  install_requires=[
      "singer-python==5.2.3",
      "requests==2.28.1",
      # ...
  ]
