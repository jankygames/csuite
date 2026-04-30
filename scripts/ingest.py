"""
scripts/ingest.py

Ingest external documents into a company's knowledge system.

Usage:
    python scripts/ingest.py --company janky_games --file docs/strategy.md
    python scripts/ingest.py --company janky_games --dir docs/
    python scripts/ingest.py --company janky_games --file data.csv --category financials
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from core.memory.ingest import ingest_file, ingest_directory


def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents into a company's knowledge system."
    )
    parser.add_argument("--company", required=True, help="Company ID")
    parser.add_argument("--file", help="Path to a single file to ingest")
    parser.add_argument("--dir", help="Path to a directory of files to ingest")
    parser.add_argument("--category", default="ingested",
                        help="Category label for the ingested content")
    args = parser.parse_args()

    if not args.file and not args.dir:
        parser.error("Provide --file or --dir")

    if args.file:
        result = ingest_file(args.company, args.file, args.category)
        print(result["message"])
        sys.exit(0 if result["success"] else 1)

    if args.dir:
        result = ingest_directory(args.company, args.dir, args.category)
        print(f"Ingested {result['entries']} entries from {result['files']} files.")
        if result["errors"]:
            for err in result["errors"]:
                print(f"  Error: {err}")
        sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
