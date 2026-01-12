from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Iterable
import requests
from bs4 import BeautifulSoup

from etl.config import BASE_URL, REQUEST_TIMEOUT, USER_AGENT

COURSE_RE = re.compile(r"^([A-Z&\s]{2,15})\s+([A-Z]?\d+[A-Z]*)$")
SECTION_RE = re.compile(r"Section:\s*([A-Z&0-9\-\.]+)")
CRN_LABEL_RE = re.compile(r"Course Number\s*\(CRN\):")
CRN_VALUE_RE = re.compile(r"\b(\d{4,6})\b")
INSTRUCTOR_RE = re.compile(r"[A-Z'\-]+,\s*[A-Z'\-]+(?:\s+[A-Z'\-]+)?")


@dataclass
class ClassRow:
    quarter: str
    subject: str
    course: str
    title: str
    section: str
    crn: str
    instructor: Optional[str]
    days_time: Optional[str]
    room: Optional[str]
    modality: Optional[str]


def extract_foothill_classes(
    quarter: str,
    dept: str = "CS",
    availability: str = "all",      # "all" | "open" | "waitlist" (matches UI wording)
    modality: str = "anymodality",  # "anymodality" | "online" | "inperson" etc (site uses these)
    location: str = "anywhere",     # "anywhere" | "foothill" | "sunnyvale" | "online" ...
    oer: str = "any",
    time: str = "Any Time",
    ge_area: str = "any",
    a_day: str = "A",
    session: Optional[requests.Session] = None,
) -> list[ClassRow]:
    """
    Extract: call the public schedule page with query params and parse out sections.
    Returns a list of ClassRow, one per section/CRN.

    Quarter example values on the site look like 2026W / 2026S etc. :contentReference[oaicite:1]{index=1}
    """
    sess = session or requests.Session()
    r = sess.get(
        BASE_URL,
        params={
            "Quarter": quarter,
            "dept": dept,              # "CS" works; "every" means all
            "availability": availability,
            "modality": modality,
            "location": location,
            "oer": oer,
            "time": time,
            "GEArea": ge_area,
            "ADay": a_day,
            "type": "any",
            "srchcrn": "",
            "srchinst": "",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    def _text(el) -> str:
        return el.get_text(" ", strip=True)

    def _looks_like_title(t: str) -> bool:
        if not t or len(t) <= 3:
            return False
        if "Course Number (CRN)" in t:
            return False
        if t.startswith("Section:"):
            return False
        if INSTRUCTOR_RE.fullmatch(t):
            return False
        return True

    def _parse_course_id(t: str) -> tuple[Optional[str], Optional[str]]:
        if not t:
            return None, None
        def _normalize_course(course: str) -> str:
            m = re.match(r"^([A-Z]*)(0*)(\d+)([A-Z]*)$", course)
            if not m:
                return course
            prefix, _, num, suffix = m.groups()
            return f"{prefix}{int(num)}{suffix}"

        m_course = COURSE_RE.match(t)
        if m_course:
            subject = "".join(m_course.group(1).split())
            course = _normalize_course(m_course.group(2))
            return subject, course
        parts = t.split()
        if len(parts) < 2:
            return None, None
        subject = "".join(parts[:-1])
        course = _normalize_course(parts[-1])
        return subject, course

    def _parse_section(section_text: str) -> tuple[Optional[str], Optional[str]]:
        if not section_text:
            return None, None
        m = re.match(r"^([A-Z&]+)-([A-Z0-9\.]+)-", section_text)
        if not m:
            return None, None
        subject, course = m.group(1), m.group(2)
        # Normalize leading zeros to align with course headers (e.g., 001A -> 1A).
        course = re.sub(r"\b0+(\d)", r"\1", course)
        return subject, course

    def _extract_meet_fields(section_el) -> tuple[Optional[str], Optional[str], Optional[str]]:
        rooms = []
        days_times = []
        instructors = []
        for row in section_el.select("div.meet-tr"):
            cells = [_text(c) for c in row.select("div.meet-td")]
            if len(cells) < 4:
                continue
            rooms.append(cells[1])
            days_times.append(cells[2])
            instructors.append(cells[3])

        def _join(values: list[str]) -> Optional[str]:
            values = [v for v in values if v]
            if not values:
                return None
            # Preserve order while deduping.
            return "; ".join(dict.fromkeys(values))

        return _join(rooms), _join(days_times), _join(instructors)

    def _find_modality(section_el) -> Optional[str]:
        strong = section_el.find("strong", string=lambda s: s and s.strip().startswith("Modality"))
        if not strong:
            return None
        text = strong.parent.get_text(" ", strip=True)
        if ":" not in text:
            return None
        return text.split(":", 1)[1].strip() or None

    def _title_for_course_id(course_id_h3) -> Optional[str]:
        if not course_id_h3:
            return None
        el = course_id_h3
        for _ in range(120):
            el = el.find_next()
            if not el:
                return None
            if el.name == "h3" and "fh_course-id" in (el.get("class") or []):
                return None
            if el.name == "h3" and "fh_course-head" in (el.get("class") or []):
                t = _text(el)
                return t if _looks_like_title(t) else None
        return None

    def _find_context(
        start_el,
        subject_hint: Optional[str],
        course_hint: Optional[str],
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if subject_hint and course_hint:
            scan = start_el
            for _ in range(600):
                scan = scan.find_previous("h3", class_="fh_course-id")
                if not scan:
                    break
                s_subj, s_course = _parse_course_id(_text(scan))
                if s_subj == subject_hint and s_course == course_hint:
                    return s_subj, s_course, _title_for_course_id(scan)

        course_id = start_el.find_previous("h3", class_="fh_course-id")
        if course_id:
            s_subj, s_course = _parse_course_id(_text(course_id))
            return s_subj, s_course, _title_for_course_id(course_id)

        return None, None, None

    rows: list[ClassRow] = []
    crn_nodes = soup.find_all(string=CRN_LABEL_RE)
    if not crn_nodes:
        print(f"No CRN markers found; URL: {r.url} (status {r.status_code})")
        with open("debug_no_crn.html", "w", encoding="utf-8") as f:
            f.write(r.text)

    for node in crn_nodes:
        crn_source = None
        if getattr(node, "parent", None) is not None:
            crn_source = node.parent.parent or node.parent
        crn_match = CRN_VALUE_RE.search(_text(crn_source) if crn_source else str(node))
        if not crn_match:
            continue
        crn = crn_match.group(1)

        section = None
        scan = node.parent
        for _ in range(80):
            scan = scan.find_previous()
            if not scan:
                break
            sm = SECTION_RE.search(_text(scan))
            if sm:
                section = sm.group(1)
                break

        sec_subject, sec_course = _parse_section(section) if section else (None, None)
        subject, course, title = _find_context(node.parent, sec_subject, sec_course)

        section_el = node.parent.find_parent(class_="section") or node.parent.find_parent(class_="fh_sched-wrap")
        if section_el:
            room, days_time, instructor = _extract_meet_fields(section_el)
            modality_val = _find_modality(section_el)
        else:
            instructor = None
            days_time = None
            room = None
            modality_val = None

        dept_code = dept.split("|", 1)[0] if dept else dept
        if dept_code != "every" and subject and subject != dept_code:
            continue

        if not (subject and course) and section:
            if sec_subject and sec_course:
                subject = subject or sec_subject
                course = course or sec_course

        if not (subject and course and title and section):
            continue

        rows.append(
            ClassRow(
                quarter=quarter,
                subject=subject,
                course=course,
                title=title,
                section=section,
                crn=crn,
                instructor=instructor,
                days_time=days_time,
                room=room,
                modality=modality_val,
            )
        )

    return rows
