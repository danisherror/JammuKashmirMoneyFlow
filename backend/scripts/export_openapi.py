"""
Write the API's OpenAPI schema to a file, without starting the server or a database.

The frontend's TypeScript types are generated from this file
(frontend/src/lib/api-schema.ts, via `npm run gen:api`), so the two can't drift apart.
After changing api/schemas.py or a route's response_model, run from the repo root:

    cd backend && python -m scripts.export_openapi ../frontend/openapi.json
    cd ../frontend && npm run gen:api

CI runs both and fails if either file changes.
"""
import argparse
import json
import sys
from pathlib import Path


def openapi_json() -> str:
    from main import app   # importing doesn't start the lifespan (DB, scheduler)
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("output", nargs="?", help="File to write; stdout when omitted")
    args = parser.parse_args(argv)
    text = openapi_json()
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
