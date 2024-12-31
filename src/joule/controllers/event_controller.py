from aiohttp import web
from sqlalchemy.orm import Session
from joule.models import EventStream, EventStore, event_stream
from joule.constants import ApiErrorMessages
from joule.controllers.helpers import read_json, validate_query_parameters
from joule.utilities.validators import validate_event_filter
from joule.models import folder, Folder
from joule.errors import ConfigurationError
from joule import app_keys

async def info(request: web.Request):
    db: Session = request.app[app_keys.db]
    event_store: EventStore = request.app[app_keys.event_store]
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db, stream_type=EventStream)
    elif 'id' in request.query:
        my_stream = db.get(EventStream, request.query["id"])
    else:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.specify_id_or_path)
    if my_stream is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.stream_does_not_exist)
    stream_info = await event_store.info([my_stream])
    ## NOTE: this endpoint supports two separate API calls- event_stream_get and event_stream_info
    # The JSON response has data for both
    return web.json_response(my_stream.to_json(stream_info))


async def move(request: web.Request):
    db: Session = request.app[app_keys.db]
    body = await read_json(request)
    # find the stream
    if 'src_path' in body:
        my_stream = folder.find_stream_by_path(body['src_path'], db, stream_type=EventStream)
    elif 'src_id' in body:
        my_stream = db.get(EventStream, body["src_id"])
    else:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.specify_id_or_path)
    if my_stream is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.stream_does_not_exist)
    if my_stream.locked:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.stream_is_locked)
    # find or create the destination folder
    if 'dest_path' in body:
        try:
            destination = folder.find(body['dest_path'], db, create=True)
        except ConfigurationError as e:
            raise web.HTTPBadRequest(reason="Destination error: %s" % str(e))
    elif 'dest_id' in body:
        destination = db.get(Folder, body["dest_id"])
    else:
        raise web.HTTPBadRequest(reason="specify a destination")
    # make sure name is unique in this destination
    existing_names = [s.name for s in destination.data_streams + destination.event_streams]
    if my_stream.name in existing_names:
        db.rollback()
        raise web.HTTPBadRequest(reason="stream with the same name exists in the destination folder")
    my_stream.folder.touch()
    destination.event_streams.append(my_stream)
    destination.touch()
    db.commit()
    return web.json_response({"stream": my_stream.to_json()})


async def create(request):
    db: Session = request.app[app_keys.db]
    event_store: EventStore = request.app[app_keys.event_store]
    body = await read_json(request)

    if 'stream' not in body:
        raise web.HTTPBadRequest(reason="provide a stream")

    # find or create the destination folder
    if 'dest_path' in body:
        try:
            destination = folder.find(body['dest_path'], db, create=True)
        except ConfigurationError as e:
            raise web.HTTPBadRequest(reason="Destination error: %s" % str(e))
    elif 'dest_id' in body:
        destination = db.get(Folder, body["dest_id"])
    else:
        raise web.HTTPBadRequest(reason="specify a destination")

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
    await event_store.create(new_stream)
    return web.json_response(data=new_stream.to_json())


async def update(request: web.Request):
    db: Session = request.app[app_keys.db]
    body = await read_json(request)
    if 'id' not in body or body['id'] is None:
        raise web.HTTPBadRequest(reason="Invalid request: specify id")

    my_stream: EventStream = db.get(EventStream, body['id'])
    if my_stream is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.stream_does_not_exist)
    if my_stream.locked:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.stream_is_locked)
    if 'stream' not in body:
        raise web.HTTPBadRequest(reason="Invalid request: specify stream as JSON")
    try:
        attrs = dict(body['stream'])
    except ValueError:
        raise web.HTTPBadRequest(reason="error: [stream] attribute must be JSON")
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
        raise web.HTTPBadRequest(reason="Invalid stream specification: %s" % e)
    return web.json_response(data=my_stream.to_json())


async def delete(request):
    db: Session = request.app[app_keys.db]
    data_store: EventStore = request.app[app_keys.event_store]
    # find the requested stream
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db,
                                               stream_type=EventStream)
    elif 'id' in request.query:
        my_stream = db.get(EventStream, request.query["id"])
    else:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.specify_id_or_path)
    if my_stream is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.stream_does_not_exist)
    if my_stream.locked:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.stream_is_locked)
    await data_store.destroy(my_stream)
    my_stream.folder.touch()
    db.delete(my_stream)
    db.commit()
    return web.Response(text="ok")


# ----- data actions ----

async def write_events(request):
    db: Session = request.app[app_keys.db]
    event_store: EventStore = request.app[app_keys.event_store]
    body = await read_json(request)

    # find the requested stream
    if 'path' in body:
        my_stream = folder.find_stream_by_path(body['path'], db,
                                               stream_type=EventStream)
    elif 'id' in body:
        my_stream = db.get(EventStream, body["id"])
    else:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.specify_id_or_path)
    if my_stream is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.stream_does_not_exist)
    if 'events' not in body:
        raise web.HTTPBadRequest(reason="specify events to add")
    # make sure the events belong to this stream, if event_stream_id does not match
    # this stream's ID, create a new event, otherwise copying events to a new stream
    # may lead to updating existing events (overwriting them) if the ID's collide
    events = body['events']
    for event in events:
        if 'event_stream_id' not in event:
            raise web.HTTPBadRequest(reason="all events must have an event_stream_id")
        if event['event_stream_id'] != my_stream.id:
            # this must have been copied from another stream, it is a new event, not an update
            event['id'] = None
            event['event_stream_id'] = my_stream.id
    events = await event_store.upsert(my_stream, events)
    return web.json_response(data={'count': len(events), 'events': events})


async def count_events(request):
    db: Session = request.app[app_keys.db]
    event_store: EventStore = request.app[app_keys.event_store]
    # find the requested stream
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db,
                                               stream_type=EventStream)
    elif 'id' in request.query:
        my_stream = db.get(EventStream, request.query["id"])
    else:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.specify_id_or_path)
    if my_stream is None:
        raise web.HTTPNotFound(reason="stream does not exist")

    # parse optional parameters
    params = {'start': None, 'end': None, 'include-ongoing-events': 0}
    validate_query_parameters(params, request.query)
    json_filter = _parse_json_filter(request.query)
    
    event_count = await event_store.count(my_stream, params['start'], params['end'],
                                          json_filter=json_filter,
                                          include_on_going_events=params['include-ongoing-events'])
    return web.json_response(data={'count': event_count})


async def read_events(request):
    db: Session = request.app[app_keys.db]
    event_store: EventStore = request.app[app_keys.event_store]
    # find the requested stream
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db,
                                               stream_type=EventStream)
    elif 'id' in request.query:
        my_stream = db.get(EventStream, request.query["id"])
    else:
        raise web.HTTPBadRequest(reason="specify an id or a path")
    if my_stream is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.stream_does_not_exist)
    if 'limit' not in request.query:
        raise web.HTTPBadRequest(reason="limit parameter is required")
    try:
        limit = int(request.query['limit'])
        if limit < 0:
            raise ValueError
    except ValueError:
        raise web.HTTPBadRequest(reason="limit parameter must be an integer > 0")
    params = {'start': None, 'end': None, 'include-ongoing-events': 0}
    validate_query_parameters(params, request.query)
    json_filter = _parse_json_filter(request.query)
    
    # handle limit parameter, default is HARD, do not return unless count < limit
    if 'return-subset' not in request.query:
        event_count = await event_store.count(my_stream, params['start'], params['end'],
                                              json_filter=json_filter,
                                              include_on_going_events=params['include-ongoing-events'])
        if event_count > limit:
            # too many events, send a histogram instead
            event_hist = await event_store.histogram(my_stream, params['start'], params['end'],
                                                     json_filter=json_filter,
                                                     nbuckets=100)
            return web.json_response(data={'count': event_count, 'events': event_hist, 'type': 'histogram'})
    # if return-subset, limit is SOFT, return just that many events
    events = await event_store.extract(my_stream, params['start'], params['end'],
                                       limit=limit, json_filter=json_filter,
                                       include_on_going_events=params['include-ongoing-events'])
    return web.json_response(data={'count': len(events), 'events': events, 'type': 'events'})


async def remove_events(request):
    db: Session = request.app[app_keys.db]
    event_store: EventStore = request.app[app_keys.event_store]
    # find the requested stream
    if 'path' in request.query:
        my_stream = folder.find_stream_by_path(request.query['path'], db,
                                               stream_type=EventStream)
    elif 'id' in request.query:
        my_stream = db.get(EventStream, request.query["id"])
    else:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.specify_id_or_path)
    if my_stream is None:
        raise web.HTTPNotFound(reason=ApiErrorMessages.stream_does_not_exist)

    # parse optional parameters
    params = {'start': None, 'end': None}
    validate_query_parameters(params, request.query)
    json_filter = _parse_json_filter(request.query)
    
    await event_store.remove(my_stream, params['start'], params['end'], json_filter=json_filter)
    return web.Response(text="ok")

def _parse_json_filter(query):
    # handle json filter parameter
    json_filter = None
    if 'filter' in query and query['filter'] is not None and len(query['filter']) > 0:
        try:
            json_filter = validate_event_filter(query['filter'])
        except ConfigurationError as e:
            raise web.HTTPBadRequest(reason=e)
    return json_filter
