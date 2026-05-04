"""Quick smoke script for optional CLI wrappers."""

from cli_backends import cursor_exec, CLIBackendError


def main() -> None:
    try:
        print(cursor_exec("Say 'adapter ready' and nothing else."))
    except CLIBackendError as exc:
        print(f"adapter error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
