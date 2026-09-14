from __future__ import annotations
import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="FleetCast: verified real-data forecasting case study")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare", help="Download January/February 2025 TLC yellow trips; aggregate with SQL")
    run_parser = sub.add_parser("run", help="Train, validate and evaluate the frozen real-data benchmark")
    run_parser.add_argument("--output", type=Path, default=Path("artifacts/first-run"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "prepare":
            from .data import prepare
            prepare(root)
        else:
            from .model import run
            output = args.output if args.output.is_absolute() else root / args.output
            run(root, output)
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        parser.exit(1, f"FleetCast stopped: {exc}\n")


if __name__ == "__main__":
    main()
