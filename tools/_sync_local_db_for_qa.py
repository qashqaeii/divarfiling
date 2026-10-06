"""One-off local DB sync for listing_detail QA — adds missing CRMProperty columns from 0069."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "db.sqlite3"
ADDS = [
    ("workspace_crmproperty", "postal_code", "varchar(10) NOT NULL DEFAULT ''"),
    ("workspace_crmproperty", "land_area", "REAL"),
    ("workspace_crmproperty", "frontage_width", "REAL"),
    ("workspace_crmproperty", "has_wardrobe", "bool NOT NULL DEFAULT 0"),
    ("workspace_crmproperty", "has_two_corner", "bool NOT NULL DEFAULT 0"),
    ("workspace_crmproperty", "has_two_access", "bool NOT NULL DEFAULT 0"),
    ("workspace_crmproperty", "has_wallpaper", "bool NOT NULL DEFAULT 0"),
    ("workspace_crmproperty", "has_knauf", "bool NOT NULL DEFAULT 0"),
    ("workspace_crmproperty", "has_lighting", "bool NOT NULL DEFAULT 0"),
]


def main():
    conn = sqlite3.connect(DB)
    for table, col, typedef in ADDS:
        existing = {r[1] for r in conn.execute(f"pragma table_info({table})").fetchall()}
        if col in existing:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        print(f"added {table}.{col}")
    conn.commit()


if __name__ == "__main__":
    main()
