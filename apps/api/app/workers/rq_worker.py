from app.workers.worker_runtime import run_worker


def main() -> None:
    run_worker(local_mode=False)


if __name__ == "__main__":
    main()
