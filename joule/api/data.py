
from .session import Session
from .stream import Stream
from joule.models import pipes
from joule import errors

import logging

log = logging.getLogger('joule')


async def data_write(session: Session,
                     stream: Stream,
                     pipe: pipes.Pipe):
    output_complete = False

    async def _data_sender():
        nonlocal output_complete
        try:
            while True:
                data = await pipe.read()
                if len(data) > 0:
                    yield data.tostring()
                if pipe.end_of_interval:
                    yield pipes.interval_token(stream.layout).tostring()
                pipe.consume(len(data))
        except pipes.EmptyPipe:
            pass
        output_complete = True

    while not output_complete:
            try:
                resp = await session.post("/data",
                                          params={"id": stream.id},
                                          data=_data_sender())
                if resp.status != 200:  # pragma: no cover
                    msg = await resp.text()
                    log.error("Error writing output [%s]: %s" % (stream.name, msg))
                    return
            except errors.ApiError as e:  # pragma: no cover
                log.info("Error submitting data to joule [%s], retrying" % str(e))
