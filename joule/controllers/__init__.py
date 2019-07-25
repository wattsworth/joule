from aiohttp import web
from joule.controllers import (
    root_controller,
    stream_controller,
    folder_controller,
    data_controller,
    module_controller,
    interface_controller,
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
    # --- stream routes ---
    web.get('/streams.json', stream_controller.index),
    web.get('/stream.json', stream_controller.info),
    web.put('/stream/move.json', stream_controller.move),
    web.put('/stream.json', stream_controller.update),
    web.post('/stream.json', stream_controller.create),
    web.delete('/stream.json', stream_controller.delete),
    # --- folder routes ---
    web.get("/folder.json", folder_controller.info),
    web.put('/folder/move.json', folder_controller.move),
    web.put('/folder.json', folder_controller.update),
    web.delete('/folder.json', folder_controller.delete),
    # --- data routes ---
    web.get('/data', data_controller.read),
    web.get('/data.json', data_controller.read_json),
    web.get('/data/intervals.json', data_controller.intervals),
    web.post('/data', data_controller.write),
    web.delete('/data', data_controller.remove),
    # --- module routes ---
    web.get('/modules.json', module_controller.index),
    web.get('/module.json', module_controller.info),
    web.get('/module/logs.json', module_controller.logs),
    # --- interface routes ---
    web.get('/interface/{id}', interface_controller.proxy),
    web.get('/interface/{id}/{path:.*}', interface_controller.proxy),
    web.post('/interface/{id}/{path:.*}', interface_controller.proxy),
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
    web.get('/annotations.json', annotation_controller.index),
    web.put('/annotation.json', annotation_controller.update),
    web.post('/annotation.json', annotation_controller.create),
    web.delete('/annotation.json', annotation_controller.delete),
    web.delete('/stream/annotations.json', annotation_controller.delete_all)
]

insecure_routes = [
    ['POST', '/follower.json']
]
