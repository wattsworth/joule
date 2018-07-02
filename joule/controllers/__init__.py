from aiohttp import web
from joule.controllers import (stream_controller,
                               folder_controller,
                               data_controller,
                               module_controller)


async def index(request):
    return web.Response(text="Joule server")

routes = [
    web.get('/', index),
    # --- stream controller routes ---
    # list all streams
    web.get('/streams.json', stream_controller.index),
    web.get('/stream.json', stream_controller.info),
    web.put('/stream/move.json', stream_controller.move),
    web.put('/stream.json', stream_controller.update),
    web.post('/stream.json', stream_controller.create),
    web.delete('/stream.json', stream_controller.delete),
    # --- folder routes ---
    web.post('/folder', folder_controller.create),
    web.put('/folder', folder_controller.update),
    web.delete('/folder', folder_controller.delete),
    # --- data routes ---
    web.get('/data', data_controller.read),
    web.get('/data.json', data_controller.read_json),
    web.post('/data', data_controller.write),
    web.delete('/data', data_controller.remove),
    # --- module routes ---
    web.get('/modules', module_controller.index),
    web.get('/module', module_controller.show),
    # TODO: routes for module interface proxy
    # TODO: routes for stream tags /streams/tags
]
