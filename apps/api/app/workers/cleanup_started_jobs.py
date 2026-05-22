import json

from app.tasks.queue import cleanup_stale_started_jobs


def main() -> int:
    result = cleanup_stale_started_jobs()
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
