from etl.extract import extract_foothill_classes
from etl.transform import normalize
from etl.load import init_db, upsert
from etl.config import QUARTER, QUARTERS, DEPT


def main():
    quarters = QUARTERS or [QUARTER]

    all_rows = []
    for quarter in quarters:
        print(f"Extracting Foothill schedule for {quarter}...")
        all_rows.extend(extract_foothill_classes(quarter=quarter, dept=DEPT))

    print("Transforming...")
    clean_rows = [normalize(r) for r in all_rows]

    print("Loading into SQLite...")
    init_db()
    for row in clean_rows:
        upsert(row)

    print(f"Loaded {len(clean_rows)} classes into foothill.db")


if __name__ == "__main__":
    main()
