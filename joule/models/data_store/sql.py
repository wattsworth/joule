from joule.models.data_store.data_store import DataStore
from sqlalchemy.orm import Session


class SqlStore(DataStore):

    def __init__(self, db: Session):
        super()
        self.db = db
