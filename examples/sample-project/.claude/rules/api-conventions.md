---
paths: ["src/api/**/*.ts"]
---

All API handlers must validate request bodies with `zod` before touching the
DB, and return errors as `{ error: string }` JSON with a matching 4xx status
code — never let a raw exception reach the client.
