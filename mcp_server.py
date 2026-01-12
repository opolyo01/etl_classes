from __future__ import annotations

"""MCP server for Foothill schedule suggestions.

Exposes a single tool, `suggest_classes`, that queries the local `foothill.db`
SQLite database and returns top-N rows ordered by a simple relevance score.
Use filters like `subject`, `course`, `instructor`, etc., and/or a free-text
`query` that scores matches across multiple columns.
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

import requests
from mcp.server.fastmcp import FastMCP

from etl.config import DB


mcp = FastMCP("foothill-schedule")
DB_PATH = Path(__file__).resolve().parent / DB
RMP_BASE_URL = os.getenv("RMP_BASE_URL", "https://www.ratemyprofessors.com/graphql")
RMP_SCHOOL_ID = os.getenv("RMP_SCHOOL_ID")
RMP_TIMEOUT = float(os.getenv("RMP_TIMEOUT", "8"))


def _clamp_limit(limit: int) -> int:
    if limit < 1:
        return 1
    if limit > 100:
        return 100
    return limit


def _like(val: str) -> str:
    return f"%{val}%"


def _normalize_instructor(name: str) -> str:
    if not name:
        return name
    if "," in name:
        last, first = [p.strip() for p in name.split(",", 1)]
        if first and last:
            return f"{first} {last}"
    return name


def _fetch_rmp_teachers(query: str, school_id: str) -> list[dict[str, Any]]:
    gql = """
    query TeacherSearch($query: String!, $schoolID: ID!) {
      newSearch {
        teachers(query: $query, schoolID: $schoolID) {
          edges {
            node {
              id
              firstName
              lastName
              department
              avgRating
              numRatings
              wouldTakeAgainPercent
              avgDifficulty
              legacyId
            }
          }
        }
      }
    }
    """
    resp = requests.post(
        RMP_BASE_URL,
        json={"query": gql, "variables": {"query": query, "schoolID": school_id}},
        timeout=RMP_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    edges = (
        data.get("data", {})
        .get("newSearch", {})
        .get("teachers", {})
        .get("edges", [])
    )
    return [edge.get("node", {}) for edge in edges if edge.get("node")]


@mcp.tool()
def suggest_classes(
    query: Optional[str] = None,
    subject: Optional[str] = None,
    course: Optional[str] = None,
    title: Optional[str] = None,
    instructor: Optional[str] = None,
    days_time: Optional[str] = None,
    room: Optional[str] = None,
    modality: Optional[str] = None,
    limit: int = 10,
    include_ratings: bool = False,
) -> list[dict[str, Any]]:
    """
    Suggest classes using text search across the local SQLite schedule database.

    Args:
        query: Free-text query scored across subject, course, title, instructor,
            days_time, room, section, and modality.
        subject: Exact subject code filter (e.g., "MATH", "CS").
        course: Exact course number filter (e.g., "1A", "C1000").
        title: Substring match on title.
        instructor: Substring match on instructor.
        days_time: Substring match on days/time (e.g., "MW", "TBA").
        room: Substring match on room/location (e.g., "Online", "4605").
        modality: Substring match on modality (e.g., "Online", "In-person").
        limit: Max rows to return (1..100).
        include_ratings: When true, attach RateMyProfessors info per instructor.
            Requires RMP_SCHOOL_ID to be set.

    Returns:
        A list of rows with keys: crn, quarter, subject, course, title, section,
        instructor, days_time, room, modality, score. If include_ratings is true,
        each row may also include rmp_rating, rmp_num_ratings, rmp_would_take_again,
        rmp_difficulty, rmp_department, and rmp_profile_url.

    Examples:
        suggest_classes(query="linear algebra", subject="MATH", limit=5)
        suggest_classes(instructor="PUGH", days_time="TTh", limit=10)
    """
    limit = _clamp_limit(limit)

    where_clauses: list[str] = []
    params: list[Any] = []

    if subject:
        where_clauses.append("UPPER(subject) = UPPER(?)")
        params.append(subject)
    if course:
        where_clauses.append("UPPER(course) = UPPER(?)")
        params.append(course)
    if title:
        where_clauses.append("title LIKE ?")
        params.append(_like(title))
    if instructor:
        where_clauses.append("instructor LIKE ?")
        params.append(_like(instructor))
    if days_time:
        where_clauses.append("days_time LIKE ?")
        params.append(_like(days_time))
    if room:
        where_clauses.append("room LIKE ?")
        params.append(_like(room))
    if modality:
        where_clauses.append("modality LIKE ?")
        params.append(_like(modality))

    score_exprs: list[str] = ["0"]
    score_params: list[Any] = []

    if query:
        query_like = _like(query)
        score_exprs.extend(
            [
                "CASE WHEN UPPER(subject) = UPPER(?) THEN 5 ELSE 0 END",
                "CASE WHEN UPPER(course) = UPPER(?) THEN 4 ELSE 0 END",
                "CASE WHEN title LIKE ? THEN 3 ELSE 0 END",
                "CASE WHEN instructor LIKE ? THEN 3 ELSE 0 END",
                "CASE WHEN days_time LIKE ? THEN 2 ELSE 0 END",
                "CASE WHEN room LIKE ? THEN 2 ELSE 0 END",
                "CASE WHEN section LIKE ? THEN 2 ELSE 0 END",
                "CASE WHEN modality LIKE ? THEN 1 ELSE 0 END",
            ]
        )
        score_params.extend(
            [
                query,
                query,
                query_like,
                query_like,
                query_like,
                query_like,
                query_like,
                query_like,
            ]
        )

        query_clause = (
            "(subject LIKE ? OR course LIKE ? OR title LIKE ? OR instructor LIKE ? "
            "OR days_time LIKE ? OR room LIKE ? OR section LIKE ? OR modality LIKE ?)"
        )
        where_clauses.append(query_clause)
        params.extend(
            [
                query_like,
                query_like,
                query_like,
                query_like,
                query_like,
                query_like,
                query_like,
                query_like,
            ]
        )

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    score_sql = " + ".join(score_exprs)

    sql = f"""
        SELECT
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
            {score_sql} AS score
        FROM classes
        WHERE {where_sql}
        ORDER BY score DESC, title ASC, subject ASC, course ASC, section ASC
        LIMIT ?
    """

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    try:
        cur = db.execute(sql, [*score_params, *params, limit])
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        db.close()

    if include_ratings and RMP_SCHOOL_ID:
        cache: dict[str, dict[str, Any]] = {}
        for row in rows:
            name = row.get("instructor")
            if not name:
                continue
            if name not in cache:
                query_name = _normalize_instructor(name)
                try:
                    matches = _fetch_rmp_teachers(query_name, RMP_SCHOOL_ID)
                except Exception:
                    cache[name] = {}
                else:
                    best = max(
                        matches,
                        key=lambda m: (m.get("numRatings") or 0, m.get("avgRating") or 0),
                        default={},
                    )
                    if best:
                        cache[name] = {
                            "rmp_rating": best.get("avgRating"),
                            "rmp_num_ratings": best.get("numRatings"),
                            "rmp_would_take_again": best.get("wouldTakeAgainPercent"),
                            "rmp_difficulty": best.get("avgDifficulty"),
                            "rmp_department": best.get("department"),
                            "rmp_profile_url": (
                                f"https://www.ratemyprofessors.com/professor/{best.get('legacyId')}"
                                if best.get("legacyId")
                                else None
                            ),
                        }
                    else:
                        cache[name] = {}
            if cache[name]:
                row.update(cache[name])

    return rows


@mcp.tool()
def lookup_professor_ratings(
    instructor: str,
    school_id: Optional[str] = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Lookup professor ratings via the unofficial RateMyProfessors GraphQL API.

    Args:
        instructor: Name in "Last, First" or "First Last" form.
        school_id: Optional RateMyProfessors school ID. Defaults to RMP_SCHOOL_ID.
        limit: Max rows to return (1..20).

    Returns:
        A list of matching professors with rating and profile info.
    """
    school_id = school_id or RMP_SCHOOL_ID
    if not school_id:
        raise ValueError("RMP_SCHOOL_ID is not set")

    limit = max(1, min(limit, 20))
    query_name = _normalize_instructor(instructor)
    matches = _fetch_rmp_teachers(query_name, school_id)

    results = []
    for node in matches[:limit]:
        results.append(
            {
                "name": f"{node.get('firstName', '')} {node.get('lastName', '')}".strip(),
                "department": node.get("department"),
                "avg_rating": node.get("avgRating"),
                "num_ratings": node.get("numRatings"),
                "would_take_again": node.get("wouldTakeAgainPercent"),
                "difficulty": node.get("avgDifficulty"),
                "profile_url": (
                    f"https://www.ratemyprofessors.com/professor/{node.get('legacyId')}"
                    if node.get("legacyId")
                    else None
                ),
            }
        )

    return results


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
