#!/usr/bin/env python3
"""
Clear the triage queue: delete all scans from the database and remove uploaded image files.
Use this to start afresh (e.g. after lots of test uploads from the frontend).

Run:
  python clear_queue.py

Or clear via API (with server running):
  curl -X POST http://127.0.0.1:5001/admin/clear-queue
"""

import os
from pathlib import Path

from database import clear_all_scans, init_db

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")


def main():
    init_db()
    deleted = clear_all_scans()
    upload_dir = Path(UPLOAD_FOLDER)
    removed_files = 0
    if upload_dir.exists():
        for f in upload_dir.iterdir():
            if f.is_file():
                try:
                    f.unlink()
                    removed_files += 1
                except OSError as e:
                    print(f"Warning: could not delete {f}: {e}")
    print(f"Queue cleared: {deleted} scans removed from database, {removed_files} files deleted from {UPLOAD_FOLDER}/.")
    print("You can start afresh.")


if __name__ == "__main__":
    main()
