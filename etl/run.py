from etl.extract import extract_foothill_classes
from etl.load import init_db, upsert

def run():
    init_db()
    rows = extract_foothill_classes(quarter="2026W", dept="CS")

    for r in rows:
        upsert((
            r.crn, r.quarter, r.subject, r.course, r.title,
            r.section, r.instructor, r.days_time, r.room, r.modality
        ))

    print("Loaded", len(rows), "classes")


if __name__ == "__main__":
    run()
