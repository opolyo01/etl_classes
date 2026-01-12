import sqlite3

DB = "foothill.db"

def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS classes (
        crn TEXT PRIMARY KEY,
        quarter TEXT,
        subject TEXT,
        course TEXT,
        title TEXT,
        section TEXT,
        instructor TEXT,
        days_time TEXT,
        room TEXT,
        modality TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_classes_subject_course ON classes(subject, course)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_classes_title ON classes(title)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_classes_instructor ON classes(instructor)")
    con.commit()
    con.close()


def upsert(row):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""
    INSERT INTO classes (
        crn,
        quarter,
        subject,
        course,
        title,
        section,
        instructor,
        days_time,
        room,
        modality,
        updated_at
    )
    VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
    ON CONFLICT(crn) DO UPDATE SET
        quarter=excluded.quarter,
        subject=excluded.subject,
        course=excluded.course,
        title=excluded.title,
        section=excluded.section,
        instructor=excluded.instructor,
        days_time=excluded.days_time,
        room=excluded.room,
        modality=excluded.modality,
        updated_at=CURRENT_TIMESTAMP
    """, row)
    con.commit()
    con.close()
