# CladeCanvas UI

Next.js frontend for CladeCanvas.

## Local Development

```bash
npm install
npm run dev
```

Create `.env.local` from `.env.example` when needed:

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8600
```

The matching local API command from the repository root is:

```bash
CLADECANVAS_DEV_SQLITE=1 uvicorn cladecanvas.api.main:app --port 8600 --reload
```

Then open http://localhost:3000.

## Production

```bash
npm run build
```

Set `NEXT_PUBLIC_API_BASE` to the hosted FastAPI URL before building. The API
must include this frontend origin in `CLADECANVAS_CORS_ORIGINS`.

This app is configured with `output: "export"`, so production hosting should
serve the generated `out/` directory as a static site.
