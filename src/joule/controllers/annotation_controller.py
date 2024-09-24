from aiohttp import web
import datetime
from datetime import timezone, datetime

from sqlalchemy import desc, asc
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from joule.models.annotation import Annotation, from_json
from joule.models.data_stream import DataStream
from joule.models import folder
from joule.errors import ApiError
from joule.constants import ApiErrorMessages
from joule import app_keys
from joule.utilities import datetime_to_timestamp

async def info(request):
    db: Session = request.app[app_keys.db]

    if 'stream_id' in request.query:
        my_stream = db.get(DataStream,request.query["stream_id"])
    elif 'stream_path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['stream_path'], db, stream_type=DataStream)
    else:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.specify_id_or_path)
    if my_stream is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.stream_does_not_exist)


    count = db.query(Annotation.start).filter_by(stream_id=my_stream.id).count()
    if count > 0:
        start = db.query(Annotation.start)\
            .filter_by(stream_id=my_stream.id)\
            .order_by(asc(Annotation.start))\
            .limit(1).scalar()
        start_ts = datetime_to_timestamp(start)
        end = db.query(Annotation.start)\
            .filter_by(stream_id=my_stream.id)\
            .order_by(desc(Annotation.start))\
            .limit(1).scalar()
        end_ts = datetime_to_timestamp(end)

    else:
        start_ts = None
        end_ts = None

    return web.json_response({
        'start': start_ts,
        'end': end_ts,
        'count': count
    })


async def index(request):
    db: Session = request.app[app_keys.db]
    # specify stream_ids as array
    # optionally specify start and end
    # parse time bounds
    start, end = _parse_time_bounds(request)
    if (('stream_id' not in request.query) and
            ('stream_path' not in request.query)):
        return web.Response(text="must specify at least one stream_id or stream_path", status=400)

    response = []
    stream_ids = []
    if "stream_id" in request.query:
        stream_ids = request.query.getall("stream_id")
    if "stream_path" in request.query:
        for path in request.query.getall("stream_path"):
            stream = folder.find_stream_by_path(path, db, stream_type=DataStream)
            if stream is None:
                raise web.HTTPNotFound(reason=ApiErrorMessages.stream_does_not_exist)
            stream_ids.append(stream.id)

    for stream_id in stream_ids:
        annotations = db.query(Annotation).filter_by(stream_id=stream_id)
        if start is not None:
            annotations = annotations.filter(Annotation.start >= start)
        if end is not None:
            annotations = annotations.filter(Annotation.start <= end)
        response += [a.to_json() for a in annotations]

    return web.json_response(response)


async def update(request):
    db: Session = request.app[app_keys.db]
    if request.content_type != 'application/json':
        raise web.HTTPBadRequest(reason='content-type must be application/json')
    body = await request.json()

    if 'id' in body:
        my_annotation = db.get(Annotation, body["id"])
    else:
        raise web.HTTPBadRequest(reason="specify an id")
    if my_annotation is None:
        raise web.HTTPNotFound(reason="annotation does not exist")
    my_annotation.update_attributes(body) # cannot change timestamps
    if my_annotation.title is None or my_annotation.title == '':
        db.rollback()
        raise web.HTTPBadRequest(reason="annotation title is reqiured")
    db.commit()
    return web.json_response(my_annotation.to_json())


async def create(request):
    db: Session = request.app[app_keys.db]
    if request.content_type != 'application/json':
        raise web.HTTPBadRequest(reason='content-type must be application/json')
    body = await request.json()

    if 'stream_id' in body:
        my_stream = db.get(DataStream,body["stream_id"])
    elif 'stream_path' in body:
        my_stream = folder.find_stream_by_path(body['stream_path'], db, stream_type=DataStream)
    else:
        raise web.HTTPBadRequest(reason="specify a stream_id")
    if my_stream is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.stream_does_not_exist)

    try:
        my_annotation = from_json(body)
        if my_annotation.title is None or my_annotation.title == '':
            raise ApiError("title is reqiured")
        if my_annotation.end is not None and (my_annotation.start >= my_annotation.end):
            raise web.HTTPBadRequest(reason=ApiErrorMessages.start_must_be_before_end)
    except ApiError as e:
        raise web.HTTPBadRequest(reason=str(e))

    my_annotation.stream = my_stream
    db.add(my_annotation)
    db.commit()
    return web.json_response(my_annotation.to_json())


async def delete(request):
    db: Session = request.app[app_keys.db]
    if 'id' in request.query:
        my_annotation = db.get(Annotation,request.query["id"])
    else:
        raise web.HTTPBadRequest(reason="specify an id")
    if my_annotation is None:
        raise web.HTTPNotFound(reason="annotation does not exist")
    db.delete(my_annotation)
    db.commit()
    return web.Response(text="ok")


async def delete_all(request):
    db: Session = request.app[app_keys.db]

    if "stream_id" in request.query:
        stream_id = request.query["stream_id"]
        my_stream = db.get(DataStream,stream_id)
    elif "stream_path" in request.query:
        path = request.query["stream_path"]
        my_stream = folder.find_stream_by_path(path, db, stream_type=DataStream)
    else:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.specify_id_or_path)

    start, end = _parse_time_bounds(request)

    if my_stream is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.stream_does_not_exist)

    annotations = db.query(Annotation).filter_by(stream_id=my_stream.id)
    if start is not None:
        annotations = annotations.filter(Annotation.start >= start)
    if end is not None:
        annotations = annotations.filter(Annotation.start <= end)

    for annotation in annotations:
        db.delete(annotation)
    db.commit()
    return web.Response(text="ok")

def _parse_time_bounds(request):
    start = None
    end = None
    try:
        if 'start' in request.query:
            ts = int(request.query['start'])
            start = datetime.fromtimestamp(ts/1e6, timezone.utc)
        if 'end' in request.query:
            ts = int(request.query['end'])
            end = datetime.fromtimestamp(ts/1e6, timezone.utc)
    except ValueError:
        raise web.HTTPBadRequest(reason="[start] and [end] must be microsecond utc timestamps")
    return start, end