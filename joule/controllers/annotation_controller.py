from aiohttp import web
import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from joule.models.annotation import Annotation, from_json
from joule.models.data_stream import DataStream
from joule.models import folder
from joule.errors import ApiError

async def info(request):
    db: Session = request.app["db"]

    if 'stream_id' in request.query:
        my_stream = db.query(DataStream,request.query["stream_id"])
    elif 'stream_path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['stream_path'], db, stream_type=DataStream)
    else:
        return web.Response(text="specify a stream_id", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)


    count = db.query(Annotation.start).filter_by(stream_id=my_stream.id).count()
    if count > 0:
        start = db.query(Annotation.start)\
            .filter_by(stream_id=my_stream.id)\
            .order_by(desc(Annotation.start))\
            .limit(1).scalar()
        start_ts = int(start.replace(tzinfo=datetime.timezone.utc).timestamp() * 1e6)
        end = db.query(Annotation.start)\
            .filter_by(stream_id=my_stream.id)\
            .order_by(desc(Annotation.start))\
            .limit(1).scalar()
        end_ts = int(end.replace(tzinfo=datetime.timezone.utc).timestamp() * 1e6)

    else:
        start_ts = None
        end_ts = None

    return web.json_response({
        'start': start_ts,
        'end': end_ts,
        'count': count
    })


async def index(request):
    db: Session = request.app["db"]
    # specify stream_ids as array
    # optionally specify start and end
    # parse time bounds
    start = None
    end = None
    try:
        if 'start' in request.query:
            ts = int(request.query['start'])
            start = datetime.datetime.utcfromtimestamp(ts / 1e6)
        if 'end' in request.query:
            ts = int(request.query['end'])
            end = datetime.datetime.utcfromtimestamp(ts / 1e6)
    except ValueError:
        return web.Response(text="[start] and [end] must be microsecond utc timestamps", status=400)
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
                return web.Response(text="stream [%s] does not exist" % path, status=404)
            stream_ids.append(stream.id)

    for stream_id in stream_ids:
        annotations = db.query(Annotation).filter_by(stream_id=stream_id)
        if start is not None:
            annotations = annotations.filter(Annotation.start >= start)
        if end is not None:
            annotations = annotations.filter(Annotation.start <= end)
        data = [a.to_json() for a in annotations]
        response += [a.to_json() for a in annotations]

    return web.json_response(response)


async def update(request):
    db: Session = request.app["db"]
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)
    body = await request.json()

    if 'id' in body:
        my_annotation = db.get(Annotation, body["id"])
    else:
        return web.Response(text="specify an id", status=400)
    if my_annotation is None:
        return web.Response(text="annotation does not exist", status=404)
    my_annotation.update_attributes(body)
    if my_annotation.title is None or my_annotation.title == '':
        return web.Response(text="annotation title is reqiured")
    db.commit()
    return web.json_response(my_annotation.to_json())


async def create(request):
    db: Session = request.app["db"]
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)
    body = await request.json()

    if 'stream_id' in body:
        my_stream = db.get(DataStream,body["stream_id"])
    elif 'stream_path' in body:
        my_stream = folder.find_stream_by_path(body['stream_path'], db, stream_type=DataStream)
    else:
        return web.Response(text="specify a stream_id", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)

    try:
        my_annotation = from_json(body)
        if my_annotation.title is None or my_annotation.title == '':
            raise ApiError("title is reqiured")
    except ApiError as e:
        return web.Response(text=str(e), status=400)

    my_annotation.stream = my_stream
    db.add(my_annotation)
    db.commit()
    return web.json_response(my_annotation.to_json())


async def delete(request):
    db: Session = request.app["db"]
    if 'id' in request.query:
        my_annotation = db.get(Annotation,request.query["id"])
    else:
        return web.Response(text="specify an id", status=400)
    if my_annotation is None:
        return web.Response(text="annotation does not exist", status=404)
    db.delete(my_annotation)
    db.commit()
    return web.Response(text="ok")


async def delete_all(request):
    db: Session = request.app["db"]

    if "stream_id" in request.query:
        stream_id = request.query["stream_id"]
        my_stream = db.get(DataStream,stream_id)
    elif "stream_path" in request.query:
        path = request.query["stream_path"]
        my_stream = folder.find_stream_by_path(path, db, stream_type=DataStream)
    else:
        return web.Response(text="must specify either stream_id or stream_path", status=400)

    start = None
    end = None
    try:
        if 'start' in request.query:
            ts = int(request.query['start'])
            start = datetime.datetime.utcfromtimestamp(ts / 1e6)
        if 'end' in request.query:
            ts = int(request.query['end'])
            end = datetime.datetime.utcfromtimestamp(ts / 1e6)
    except ValueError:
        return web.Response(text="[start] and [end] must be microsecond utc timestamps", status=400)

    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)

    annotations = db.query(Annotation).filter_by(stream_id=my_stream.id)

    if start is not None:
        annotations = annotations.filter(Annotation.start >= start)
    if end is not None:
        annotations = annotations.filter(Annotation.start <= end)

    for annotation in annotations:
        db.delete(annotation)
    db.commit()
    return web.Response(text="ok")
