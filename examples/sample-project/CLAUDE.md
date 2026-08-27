# CLAUDE.md

## Project Purpose

`sample-project` is a small Node/Express + Postgres API service that manages a
"widgets" inventory: CRUD endpoints backed by a Postgres table, fronted by a
thin Express router layer. Business logic lives in `src/services/`, HTTP
handlers in `src/api/`, and DB access goes through `src/db/pool.ts` (no ORM).

## Key Commands

- `npm run dev` — start the API with hot reload on port 3000
- `npm test` — run the Jest test suite (`src/**/*.test.ts`)
- `npm run migrate` — apply pending Postgres migrations in `migrations/`

## Architecture Notes

Requests flow `router → controller → service → db/pool.ts`. Controllers only
handle HTTP concerns (status codes, body parsing); all validation and business
rules live in the service layer so they're reusable from background jobs.
