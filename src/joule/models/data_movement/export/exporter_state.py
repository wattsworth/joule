from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import Session
from joule.models.meta import Base
from datetime import datetime, timezone
from dataclasses import dataclass

@dataclass
class ExporterState:
    last_timestamp: int

    def to_record(self):
        return {"last_timestamp": int(self.last_timestamp)} #ensure value is JSON serializable
    
class ExporterStateRecord(Base):
    __tablename__ = 'exporter_state'
    __table_args__ = {"schema": "metadata"}

    name: str = Column(String, nullable=False)
    source_type: str = Column(String, nullable=False)
    source_label: str = Column(String, nullable=True)
    state: dict = Column(JSON, nullable=False)
    updated_at: DateTime = Column(DateTime(timezone=True), nullable=False)
    id: int = Column(Integer, primary_key=True)
    
class ExporterStateService:
    def __init__(self, db:Session):
        self.db = db

    def get(self, exporter_name:str, source_type:str, source_label:str) -> ExporterState:
        state_data = self.db.query(ExporterStateRecord)\
                            .filter_by(name=exporter_name,
                                       source_type=source_type,
                                       source_label=source_label)\
                            .first().state
        return ExporterState(**state_data)

    def save(self, exporter_name:str, source_type:str, source_label:str, state: ExporterState) -> None:
        state = ExporterStateRecord(name=exporter_name,
                                    source_type=source_type,
                                    source_label=source_label,
                                    state=state.to_record(),
                                    updated_at=datetime.now(tz=timezone.utc))
        self.db.add(state)