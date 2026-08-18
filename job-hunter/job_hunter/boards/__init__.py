"""Board scrapers. Each board fetches jobs and returns Job objects.

A failing board must never kill a discovery run — orchestrator wraps each
board in try/except and logs the error.
"""

from job_hunter.boards.base import Board
from job_hunter.boards.remoteok import RemoteOKBoard
from job_hunter.boards.remote4africa import Remote4AfricaBoard
from job_hunter.boards.weworkremotely import WeWorkRemotelyBoard
from job_hunter.boards.himalayas import HimalayasBoard
from job_hunter.boards.remotive import RemotiveBoard
from job_hunter.boards.persona import PersonaBoard
from job_hunter.boards.workingnomads import WorkingNomadsBoard
from job_hunter.boards.jobicy import JobicyBoard
from job_hunter.boards.ats import ATSBoard

BOARDS: dict[str, Board] = {
    "remoteok": RemoteOKBoard(),
    "remote4africa": Remote4AfricaBoard(),
    "weworkremotely": WeWorkRemotelyBoard(),
    "himalayas": HimalayasBoard(),
    "remotive": RemotiveBoard(),
    "persona": PersonaBoard(),
    "workingnomads": WorkingNomadsBoard(),
    "jobicy": JobicyBoard(),
    "ats": ATSBoard(),
}
