"""The structured generation catalog for the v1 Career Knowledge Base.

Each entry is the *generation input* for one broad career path: the factual
spine (identity, tags, education, skills, salary bands, outlook scores,
cities, relationships) that `tools/generate_career_knowledge.py` expands into
the full canonical JSON schema. Entries are grouped into the 16 foundational
industries.

Entry tuple fields (in order):
    name, career_family, tags (space-separated), student_summary,
    school_subjects, college_degrees, core_skills, technologies
    (";"-separated), salary_entry_lpa, salary_senior_lpa, difficulty (1-5),
    competition (1-5), demand (0-1), automation_risk (0-1), remote (0-1),
    major_hiring_cities, related_careers (";"-separated career names).
"""

from .part1 import INDUSTRIES_1_6
from .part2 import INDUSTRIES_7_11
from .part3 import INDUSTRIES_12_16

INDUSTRIES: dict = {**INDUSTRIES_1_6, **INDUSTRIES_7_11, **INDUSTRIES_12_16}

__all__ = ["INDUSTRIES"]
