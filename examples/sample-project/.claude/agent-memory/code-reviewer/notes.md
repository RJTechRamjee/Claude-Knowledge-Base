# code-reviewer notes

- 2026-08-12: `src/api/widgets.ts` historically forgets to validate the
  `quantity` field — double-check it on every review.
- Team prefers `describe`/`it` blocks named after the HTTP method + route.
