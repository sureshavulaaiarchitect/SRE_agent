from sqlalchemy.orm import declarative_base

Base = declarative_base()

from .incident import Incident
from .remediation_action import RemediationAction
from .activity import Activity
