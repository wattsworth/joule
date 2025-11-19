
from typing import List
from joule import errors
from joule.constants import EndPoints
from joule.utilities.archive_tools import ImportLogger
from .session import BaseSession

async def archive_upload(session: BaseSession,
                         path: str) -> ImportLogger:
    with open(path, 'rb') as f:
        resp = await session.post(EndPoints.archive, data=f)
        logger = ImportLogger()
        logger.from_json(resp)
        return logger