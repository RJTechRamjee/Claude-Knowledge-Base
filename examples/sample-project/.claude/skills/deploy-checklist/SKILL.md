---
name: deploy-checklist
description: Run through the pre-deploy checklist for sample-project before shipping to production.
---

Before deploying, verify in order:

1. `npm test` passes with no skipped suites
2. `npm run migrate -- --dry-run` shows no pending destructive migrations
3. The changelog entry for this release exists in `CHANGELOG.md`

Report any failing step instead of proceeding.
