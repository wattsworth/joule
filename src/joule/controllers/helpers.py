from aiohttp import web
from joule.constants import ApiErrorMessages
from joule.models import DataStream, folder
from sqlalchemy.orm import Session
import json

async def read_json(request: web.Request):
    if request.content_type != 'application/json':
        raise web.HTTPBadRequest(reason='content-type must be application/json')
    try:
        return await request.json()
    except json.JSONDecodeError:
        raise web.HTTPBadRequest(reason='invalid json')

def validate_query_parameters(params, query):
    # populate the params dictionary with query parameters if they exist
    # return the parsed json_filter parameter if it exists
    try:
        for param in params:
            if param in query:
                params[param] = int(query[param])
    except ValueError:
        raise web.HTTPBadRequest(reason=ApiErrorMessages.f_parameter_must_be_an_int.format(parameter=param))
    
    # make sure parameters make sense
    if ((params['start'] is not None and params['end'] is not None) and
            (params['start'] >= params['end'])):
        raise web.HTTPBadRequest(reason=ApiErrorMessages.start_must_be_before_end)

def get_stream_from_request_params(request: web.Request, db: Session) -> DataStream:
    if 'path' in request.query:
        stream = folder.find_stream_by_path(request.query['path'], db, stream_type=DataStream)
    elif 'id' in request.query:
        stream = db.get(DataStream,request.query["id"])
    else:
        raise web.HTTPBadRequest(reason="specify an id or a path")
    if stream is None:
        raise web.HTTPNotFound(reason="stream does not exist")
    return stream