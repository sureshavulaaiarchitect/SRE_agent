from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from datetime import datetime
import uuid
from . import Base

class Activity(Base):
    __tablename__ = "activities"

    id        = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    type      = Column(String, nullable=False) # incident, remediation, approval, alert
    message   = Column(String, nullable=False)
    severity  = Column(String, default="info") # critical, high, medium, low
    actor     = Column(String, default="system") # system, ai, user, playbook
    details   = Column(Text) # JSON or structured data
    
    # Optional link to incident
    incident_id = Column(String, ForeignKey("incidents.id"), nullable=True)

