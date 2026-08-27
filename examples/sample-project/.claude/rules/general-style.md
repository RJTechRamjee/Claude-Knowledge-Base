---
---

Use 2-space indentation. Prefer named exports over default exports. Keep
service functions pure where possible — pass a DB client in rather than
importing `pool` directly, so services stay testable without a live DB.
