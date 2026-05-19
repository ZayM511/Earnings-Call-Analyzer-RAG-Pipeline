"""Minimal speaker-name -> role lookup for Mag 7 calls.

Used when the transcript itself provides no role hint (Tesla format) or when
a speaker turn's `role_hint` field is missing. Maintain this by hand as
execs change.

Source of truth: each company's investor relations page on the date of the
call. We only need the executive-tagged people; analysts default to
'Analyst' in the parser when they appear after the QA cue.
"""

from __future__ import annotations

MAG7_EXEC_LOOKUP: dict[str, str] = {
    # Apple
    "Tim Cook": "CEO",
    "Timothy Cook": "CEO",
    "Timothy Donald Cook": "CEO",
    "Luca Maestri": "CFO",
    "Kevan Parekh": "CFO",
    "Suhasini Chandramouli": "IR",
    # Microsoft
    "Satya Nadella": "CEO",
    "Amy Hood": "CFO",
    "Brett Iversen": "IR",
    # Alphabet
    "Sundar Pichai": "CEO",
    "Ruth Porat": "CFO",
    "Anat Ashkenazi": "CFO",
    "Philipp Schindler": "Other",  # Chief Business Officer
    "Jim Friedland": "IR",
    # Amazon
    "Andy Jassy": "CEO",
    "Brian Olsavsky": "CFO",
    "Dave Fildes": "IR",
    # Meta
    "Mark Zuckerberg": "CEO",
    "Susan Li": "CFO",
    "Kenneth Dorell": "IR",
    "Krishna Gade": "IR",
    # NVIDIA
    "Jensen Huang": "CEO",
    "Colette Kress": "CFO",
    "Colette M. Kress": "CFO",
    "Simona Jankowski": "IR",
    "Stewart Stecker": "IR",
    # Tesla
    "Elon Musk": "CEO",
    "Vaibhav Taneja": "CFO",
    "Zachary Kirkhorn": "CFO",  # left in 2023, kept for historical robustness
    "Travis Axelrod": "IR",
}
