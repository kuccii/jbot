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
from job_hunter.boards.arc import ArcBoard
from job_hunter.boards.foundthejob import FoundTheJobBoard
from job_hunter.boards.opentrain import OpenTrainBoard
from job_hunter.boards.dynamitejobs import DynamiteJobsBoard
from job_hunter.boards.trulyremote import TrulyRemoteBoard
from job_hunter.boards.gig_platforms import GigPlatformsBoard
from job_hunter.boards.indeed import IndeedBoard
from job_hunter.boards.startupjobs import StartupJobsBoard
from job_hunter.boards.meetfrank import MeetFrankBoard
from job_hunter.boards.workday import WorkdayBoard
from job_hunter.boards.alignerr import AlignerrBoard
from job_hunter.boards.outlier import OutlierBoard
from job_hunter.boards.indeed_entry import IndeedEntryBoard
from job_hunter.boards.wwr_entry import WWREntryBoard
from job_hunter.boards.searx_search import IndeedSearchBoard, VisaSponsorshipBoard

# Board name -> class mapping. The orchestrator instantiates these with
# per-run config (e.g. RemoteOKBoard needs keyword tags, ATSBoard needs
# a company list).
BOARDS: dict[str, type[Board]] = {
    "remoteok": RemoteOKBoard,
    "remote4africa": Remote4AfricaBoard,
    "weworkremotely": WeWorkRemotelyBoard,
    "himalayas": HimalayasBoard,
    "remotive": RemotiveBoard,
    "persona": PersonaBoard,
    "workingnomads": WorkingNomadsBoard,
    "jobicy": JobicyBoard,
    "ats": ATSBoard,
    "arc": ArcBoard,
    "foundthejob": FoundTheJobBoard,
    "opentrain": OpenTrainBoard,
    "dynamitejobs": DynamiteJobsBoard,
    "trulyremote": TrulyRemoteBoard,
    "gig_platforms": GigPlatformsBoard,
    "indeed": IndeedBoard,
    "indeed_entry": IndeedEntryBoard,
    "startupjobs": StartupJobsBoard,
    "meetfrank": MeetFrankBoard,
    "workday": WorkdayBoard,
    "alignerr": AlignerrBoard,
    "outlier": OutlierBoard,
    "wwr_entry": WWREntryBoard,
    "indeed_search": IndeedSearchBoard,
    "visa_sponsorship": VisaSponsorshipBoard,
}
