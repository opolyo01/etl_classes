from etl.extract import extract_foothill_classes
from etl.transform import normalize
from etl.load import init_db, upsert
from etl.config import QUARTER, DEPT


def main():
    print("Extracting Foothill schedule...")
    raw_rows = extract_foothill_classes(quarter=QUARTER, dept=DEPT)

    print("Transforming...")
    clean_rows = [normalize(r) for r in raw_rows]

    print("Loading into SQLite...")
    init_db()
    for row in clean_rows:
        upsert(row)

    print(f"Loaded {len(clean_rows)} classes into foothill.db")


if __name__ == "__main__":
    main()
