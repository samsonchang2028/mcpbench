"""Fail closed for every evaluator phase until the runtime tasks are implemented."""
import sys


def main() -> int:
    print("mcpbench: evaluator unavailable until its runtime DAG gates pass", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
