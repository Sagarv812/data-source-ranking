# Source Signal UI

React interface for the local data source ranking product.

## Commands

```bash
npm install
npm run dev
npm run build
npm run lint
```

The UI expects the FastAPI backend at `http://127.0.0.1:8000` by default.
Override with `VITE_API_BASE_URL` when needed.

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

## Current Slice

- Pastel evidence-console shell.
- API health, bundle fixtures, run history, and feedback snapshot queries.
- Placeholder review portal route at `/review/:runId`.
- Workflow actions are intentionally disabled until the next Day 6 slice.
