from aiohttp import web
from joule.controllers import (
    root_controller,
    stream_controller,
    event_controller,
    folder_controller,
    data_controller,
    module_controller,
    app_controller,
    proxy_controller,
    master_controller,
    follower_controller,
    annotation_controller)

routes = [
    web.get('/', root_controller.index),
    web.get('/db/connection.json', root_controller.db_connection),
    web.get('/dbinfo', root_controller.dbinfo),
    web.get('/version', root_controller.version),
    web.get('/version.json', root_controller.version_json),
    # --- event stream routes ---
    web.get('/event.json', event_controller.info),
    web.put('/event/move.json', event_controller.move),
    web.put('/event.json', event_controller.update),
    web.post('/event.json', event_controller.create),
    web.delete('/event.json', event_controller.delete),
    # --- event stream data routes ---
    web.get('/event/data.json', event_controller.read_events),
    web.post('/event/data.json', event_controller.write_events),
    web.delete('/event/data.json', event_controller.remove_events),
    # --- stream routes ---
    web.get('/streams.json', folder_controller.index),  # legacy support for Rails API
    web.get('/stream.json', stream_controller.info),
    web.put('/stream/move.json', stream_controller.move),
    web.put('/stream.json', stream_controller.update),
    web.post('/stream.json', stream_controller.create),
    web.delete('/stream.json', stream_controller.delete),
    # --- folder routes ---
    web.get('/folders.json', folder_controller.index),
    web.get("/folder.json", folder_controller.info),
    web.put('/folder/move.json', folder_controller.move),
    web.put('/folder.json', folder_controller.update),
    web.delete('/folder.json', folder_controller.delete),
    # --- data routes ---
    web.get('/data', data_controller.read),
    web.get('/data.json', data_controller.read_json),
    web.get('/data/intervals.json', data_controller.intervals),
    web.post('/data/decimate.json', data_controller.decimate),
    web.delete('/data/decimate.json', data_controller.drop_decimations),
    web.post('/data/consolidate.json', data_controller.consolidate),
    web.post('/data', data_controller.write),
    web.delete('/data', data_controller.remove),
    # --- module routes ---
    web.get('/modules.json', module_controller.index),
    web.get('/module.json', module_controller.info),
    web.get('/module/logs.json', module_controller.logs),
    # --- app routes ---
    web.get('/app/auth', app_controller.auth),
    web.get('/app.json', app_controller.index),

    # --- proxy routes ---
    web.get('/proxies.json', proxy_controller.index),
    web.get('/proxy.json', proxy_controller.info),
    # -- master routes --
    web.get('/masters.json', master_controller.index),
    web.post('/master.json', master_controller.add),
    web.delete('/master.json', master_controller.delete),
    # -- follower routes --
    web.get('/followers.json', follower_controller.index),
    web.post('/follower.json', follower_controller.add),
    web.delete('/follower.json', follower_controller.delete),
    # -- annotation routes --
    web.get('/annotations/info.json', annotation_controller.info),
    web.get('/annotations.json', annotation_controller.index),
    web.put('/annotation.json', annotation_controller.update),
    web.post('/annotation.json', annotation_controller.create),
    web.delete('/annotation.json', annotation_controller.delete),
    web.delete('/stream/annotations.json', annotation_controller.delete_all)
]

insecure_routes = [
    ['POST', '/follower.json']
]
