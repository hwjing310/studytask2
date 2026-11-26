"""年级规则与学籍年级的仓储（读写扩展表/列）。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from .schema import grade_label, now


@dataclass(frozen=True)
class GradeRule:
    activity_id: str
    min_grade: int
    max_grade: int

    def allows(self, grade: int) -> bool:
        return self.min_grade <= grade <= self.max_grade

    @property
    def label(self) -> str:
        if self.min_grade == self.max_grade:
            return grade_label(self.min_grade)
        return f"{grade_label(self.min_grade)}、{grade_label(self.max_grade)}"

    def to_dict(self) -> dict:
        return {
            "activity_id": self.activity_id,
            "min_grade": self.min_grade,
            "max_grade": self.max_grade,
            "label": self.label,
        }


class GradeRuleRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, activity_id: str) -> Optional[GradeRule]:
        row = self._conn.execute(
            "SELECT activity_id, min_grade, max_grade FROM ext_activity_grade_rules WHERE activity_id=?",
            (activity_id,),
        ).fetchone()
        if not row:
            return None
        return GradeRule(row["activity_id"], row["min_grade"], row["max_grade"])

    def list_all(self) -> dict[str, GradeRule]:
        rows = self._conn.execute(
            "SELECT activity_id, min_grade, max_grade FROM ext_activity_grade_rules"
        ).fetchall()
        return {r["activity_id"]: GradeRule(r["activity_id"], r["min_grade"], r["max_grade"]) for r in rows}

    def upsert(self, activity_id: str, min_grade: int, max_grade: int) -> GradeRule:
        ts = now()
        self._conn.execute(
            """INSERT INTO ext_activity_grade_rules(activity_id, min_grade, max_grade, created_at, updated_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(activity_id) DO UPDATE SET
                   min_grade=excluded.min_grade,
                   max_grade=excluded.max_grade,
                   updated_at=excluded.updated_at""",
            (activity_id, min_grade, max_grade, ts, ts),
        )
        self._conn.commit()
        return GradeRule(activity_id, min_grade, max_grade)

    def delete(self, activity_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM ext_activity_grade_rules WHERE activity_id=?", (activity_id,)
        )
        self._conn.commit()
        return cur.rowcount > 0


class StudentGradeRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_grade(self, student_id: str) -> Optional[int]:
        row = self._conn.execute(
            "SELECT grade FROM students WHERE student_id=?", (student_id,)
        ).fetchone()
        return row["grade"] if row else None

    def set_grade(self, student_id: str, grade: int) -> bool:
        cur = self._conn.execute(
            "UPDATE students SET grade=? WHERE student_id=?", (grade, student_id)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def list_students(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT student_id, name, role, grade FROM students ORDER BY student_id"
        ).fetchall()
        return [
            {
                "student_id": r["student_id"],
                "name": r["name"],
                "role": r["role"],
                "grade": r["grade"],
                "grade_label": grade_label(r["grade"]),
            }
            for r in rows
        ]
