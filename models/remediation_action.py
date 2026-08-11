from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from . import Base

class RemediationAction(Base):
    __tablename__ = "remediation_actions"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id = Column(String, ForeignKey("incidents.id", ondelete="CASCADE"))
    action      = Column(String, nullable=False)
    approved    = Column(Boolean, default=False)
    approved_by = Column(String)   # engineer username
    executed    = Column(Boolean, default=False)
    success     = Column(Boolean)
    timestamp   = Column(DateTime, default=datetime.utcnow)
    
    incident = relationship("Incident", back_populates="actions")
