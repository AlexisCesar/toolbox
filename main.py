import sys


def main() -> None:
    """Run the toolbox TUI prototype."""
    try:
        from src.tui import ToolboxTUI
    except OSError as error:
        sys.stderr.write(f"Toolbox could not start: {error}\n")
        raise SystemExit(1) from error

    app = ToolboxTUI()
    app.run()


if __name__ == "__main__":
    main()
