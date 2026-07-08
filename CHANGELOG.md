## 0.1.0
  * 403-inaccessible streams are now excluded from the catalog during discovery instead of failing entirely. [#9](https://github.com/singer-io/tap-zoho-crm/pull/9)
  * Added unit tests for discovery access-check behavior.
  * Bump singer-python to 6.8.0 and requests to 2.34.2 (CVE-2026-25645)
  * Implemented access token chaining: valid tokens are reused across runs without an extra refresh round-trip. [#10](https://github.com/singer-io/tap-zoho-crm/pull/10)
  * Added `preserve_config = True` to ensure the configuration is preserved when multiple integration tests run concurrently, preventing it from being overwritten or reset between test executions.

## 0.0.1
  * Initial Commit