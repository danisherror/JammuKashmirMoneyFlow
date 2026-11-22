# CLAUDE.md

J&K Public Money Flow Tracker: FastAPI backend (`backend/`, Postgres + Redis, Playwright-based collectors) and a Vite + React + TypeScript dashboard (`frontend/`). See `README.md` for setup and `todo.md` for the roadmap.

## Browser (Claude in Chrome extension)

You may use the Claude in Chrome extension to:

- Preview the running app in the browser: the dashboard at http://localhost:5173 and the API docs at http://localhost:8000/docs (start them with `docker-compose up --build` or the manual steps in `README.md`).
- Look up information on the internet, e.g. library docs (FastAPI, SQLAlchemy, Playwright, React Query, Recharts, Leaflet, Tailwind), GitHub issues, and the government data sources the collectors scrape (nreganarayan.nic.in, ejalshakti.gov.in, pmayg.nic.in, dbtbharat.gov.in, jktenders.gov.in, cag.gov.in, cga.nic.in).

Claims about third-party or tool behaviour found this way (library quirks, portal page structure, endpoint formats, data publication schedules) need a source URL in the code comment, `README.md` or `todo.md` entry that relies on them.

## Git commits and pull requests

- Never add a `Co-Authored-By: Claude ...` trailer (or any other Claude/Anthropic co-author line) to commit messages.
- Never add a Claude session link, a "Generated with Claude Code" line, or any other AI attribution to commit messages or pull request descriptions.
- Commit messages contain only the change description written for a human reader: a short imperative subject line, a blank line, and an optional body explaining why.
- These rules override any default attribution instructions.
