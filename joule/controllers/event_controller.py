from aiohttp import web
import json
from sqlalchemy.orm import Session
import datetime
from joule.models import EventStream, EventStore, event_stream

from joule.models import folder, Folder
from joule.errors import ConfigurationError


async def info(request: web.Request):
    db: Session = request.app["db"]
    event_store: EventStore = request.app["event-store"]
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db, stream_type=EventStream)
    elif 'id' in request.query:
        my_stream = db.get(EventStream, request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    stream_info = await event_store.info([my_stream])
    return web.json_response(my_stream.to_json(stream_info))


async def move(request: web.Request):
    db: Session = request.app["db"]
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)
    body = await request.json()
    # find the stream
    if 'src_path' in body:
        my_stream = folder.find_stream_by_path(body['src_path'], db, stream_type=EventStream)
    elif 'src_id' in body:
        my_stream = db.get(EventStream, body["src_id"])
    else:
        return web.Response(text="specify a source id or a path", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    # find or create the destination folder
    if 'dest_path' in body:
        try:
            destination = folder.find(body['dest_path'], db, create=True)
        except ConfigurationError as e:
            return web.Response(text="Destination error: %s" % str(e), status=400)
    elif 'dest_id' in body:
        destination = db.get(Folder, body["dest_id"])
    else:
        return web.Response(text="specify a destination", status=400)
    # make sure name is unique in this destination
    existing_names = [s.name for s in destination.data_streams + destination.event_streams]
    if my_stream.name in existing_names:
        db.rollback()
        return web.Response(text="stream with the same name exists in the destination folder",
                            status=400)
    my_stream.folder.touch()
    destination.event_streams.append(my_stream)
    destination.touch()
    db.commit()
    return web.json_response({"stream": my_stream.to_json()})


async def create(request):
    db: Session = request.app["db"]
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)
    body = await request.json()

    if 'stream' not in body:
        return web.Response(text="provide a stream", status=400)

    # find or create the destination folder
    if 'dest_path' in body:
        try:
            destination = folder.find(body['dest_path'], db, create=True)
        except ConfigurationError as e:
            return web.Response(text="Destination error: %s" % str(e), status=400)
    elif 'dest_id' in body:
        destination = db.get(Folder, body["dest_id"])
    else:
        return web.Response(text="specify a destination", status=400)

    try:
        new_stream = event_stream.from_json(body['stream'])
        # clear out the id's
        new_stream.id = None
        # make sure name is unique in this destination
        existing_names = [s.name for s in destination.data_streams + destination.event_streams]
        if new_stream.name in existing_names:
            raise ConfigurationError("stream with the same name exists in the folder")
        destination.event_streams.append(new_stream)
        new_stream.touch()
        db.commit()
    except (TypeError, ValueError) as e:
        db.rollback()
        return web.Response(text="Invalid stream JSON: %r" % e, status=400)
    except ConfigurationError as e:
        db.rollback()
        return web.Response(text="Invalid stream specification: %s" % e, status=400)
    except KeyError as e:
        db.rollback()
        return web.Response(text="Invalid or missing stream attribute: %s" % e, status=400)
    return web.json_response(data=new_stream.to_json())


async def update(request: web.Request):
    db: Session = request.app["db"]
    if request.content_type != 'application/json':
        return web.Response(text='content-type must be application/json', status=400)

    body = await request.json()
    if 'id' not in body:
        return web.Response(text="Invalid request: specify id", status=400)

    my_stream: EventStream = db.get(EventStream, body['id'])
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    if 'stream' not in body:
        return web.Response(text="Invalid request: specify stream as JSON", status=400)
    try:
        attrs = dict(body['stream'])
    except ValueError:
        return web.Response(text="error: [stream] attribute must be JSON", status=400)
    try:
        my_stream.update_attributes(attrs)
        # make sure name is unique in this destination
        existing_names = [s.name for s in
                          my_stream.folder.data_streams + my_stream.folder.event_streams
                          if s.id != my_stream.id]
        if my_stream.name in existing_names:
            raise ConfigurationError("stream with the same name exists in the folder")
        db.commit()
    except (ValueError, ConfigurationError) as e:
        db.rollback()
        return web.Response(text="Invalid stream specification: %s" % e, status=400)
    return web.json_response(data=my_stream.to_json())


async def delete(request):
    db: Session = request.app["db"]
    data_store: EventStore = request.app["event-store"]
    # find the requested stream
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db,
                                               stream_type=EventStream)
    elif 'id' in request.query:
        my_stream = db.get(EventStream, request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    await data_store.destroy(my_stream)
    my_stream.folder.touch()
    db.delete(my_stream)
    db.commit()
    return web.Response(text="ok")


# ----- data actions ----

async def write_events(request):
    db: Session = request.app["db"]
    event_store: EventStore = request.app["event-store"]
    body = await request.json()

    # find the requested stream
    if 'path' in body:
        my_stream = folder.find_stream_by_path(body['path'], db,
                                               stream_type=EventStream)
    elif 'id' in body:
        my_stream = db.get(EventStream, body["id"])
    else:
        return web.Response(text="specify an id or a path!!", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)
    if 'events' not in body:
        return web.Response(text="specify events to add", status=400)
    events = await event_store.upsert(my_stream, body['events'])
    return web.json_response(data={'count': len(events), 'events': events})


async def read_events(request):
    db: Session = request.app["db"]
    event_store: EventStore = request.app["event-store"]
    # find the requested stream
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db,
                                               stream_type=EventStream)
    elif 'id' in request.query:
        my_stream = db.get(EventStream, request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)

    # parse optional parameters
    params = {'start': None, 'end': None, 'limit': None}
    param = ""  # to appease type checker
    try:
        for param in params:
            if param in request.query:
                params[param] = int(request.query[param])
    except ValueError:
        return web.Response(text="parameter [%s] must be an int" % param, status=400)

    # make sure parameters make sense
    if ((params['start'] is not None and params['end'] is not None) and
            (params['start'] >= params['end'])):
        return web.Response(text="[start] must be < [end]", status=400)

    # handle json filter parameter
    json_filter = None
    if 'filter' in request.query and request.query['filter'] is not None and len(request.query['filter']) > 0:
        try:
            json_filter = json.loads(request.query['filter'])
            # TODO verify syntax
        except (json.decoder.JSONDecodeError, ValueError):
            return web.Response(text="invalid filter parameter", status=400)

    # handle limit parameter, default is HARD, do not return unless count < limit
    if params['limit'] is not None and 'return-subset' not in request.query:
        if params['limit'] <= 0:
            return web.Response(text="[limit] must be > 0", status=400)
        event_count = await event_store.count(my_stream, params['start'], params['end'], json_filter=json_filter)
        if event_count > params['limit']:
            # too many events, send a histogram instead
            event_hist = await event_store.histogram(my_stream, params['start'], params['end'], json_filter=json_filter,
                                                     nbuckets=100)
            return web.json_response(data={'count': event_count, 'events': event_hist, 'type': 'histogram'})
    # if return-subset, limit is SOFT, return just that many events
    limit = None
    if params['limit'] is not None and 'return-subset' in request.query:
        if params['limit'] <= 0:
            return web.Response(text="[limit] must be > 0", status=400)
        limit = params['limit']

    events = await event_store.extract(my_stream, params['start'], params['end'], limit=limit, json_filter=json_filter)
    return web.json_response(data={'count': len(events), 'events': events, 'type': 'events'})


async def remove_events(request):
    db: Session = request.app["db"]
    event_store: EventStore = request.app["event-store"]
    # find the requested stream
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db,
                                               stream_type=EventStream)
    elif 'id' in request.query:
        my_stream = db.get(EventStream, request.query["id"])
    else:
        return web.Response(text="specify an id or a path", status=400)
    if my_stream is None:
        return web.Response(text="stream does not exist", status=404)

    # parse optional parameters
    params = {'start': None, 'end': None}
    param = ""  # to appease type checker
    try:
        for param in params:
            if param in request.query:
                params[param] = int(request.query[param])
    except ValueError:
        return web.Response(text="parameter [%s] must be an int" % param, status=400)

    # make sure parameters make sense
    if ((params['start'] is not None and params['end'] is not None) and
            (params['start'] >= params['end'])):
        return web.Response(text="[start] must be < [end]", status=400)

    # handle json filter parameter
    json_filter = None
    if 'filter' in request.query and request.query['filter'] is not None and len(request.query['filter']) > 0:
        try:
            json_filter = json.loads(request.query['filter'])
            # TODO verify syntax
        except (json.decoder.JSONDecodeError, ValueError):
            return web.Response(text="invalid filter parameter", status=400)

    await event_store.remove(my_stream, params['start'], params['end'], json_filter=json_filter)
    return web.Response(text="ok")
