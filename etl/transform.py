from typing import Tuple
from etl.extract import ClassRow


def normalize(r: ClassRow) -> Tuple:
    return (
        r.crn,
        r.quarter,
        r.subject,
        r.course,
        r.title.title(),       # clean capitalization
        r.section,
        r.instructor,
        r.days_time,
        r.room,
        r.modality,
    )
