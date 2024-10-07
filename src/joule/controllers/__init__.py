from aiohttp import web
from joule.constants import EndPoints

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
    web.get(EndPoints.root, root_controller.index),
    web.get(EndPoints.db_connection, root_controller.db_connection),
    web.get(EndPoints.db_info, root_controller.dbinfo),
    web.get(EndPoints.version, root_controller.version),
    web.get(EndPoints.version_json, root_controller.version_json),
    # --- event stream routes ---
    web.get(EndPoints.event, event_controller.info),
    web.put(EndPoints.event_move, event_controller.move),
    web.put(EndPoints.event, event_controller.update),
    web.post(EndPoints.event, event_controller.create),
    web.delete(EndPoints.event, event_controller.delete),
    # --- event stream data routes ---
    web.get(EndPoints.event_data, event_controller.read_events),
    web.get(EndPoints.event_data_count, event_controller.count_events),
    web.post(EndPoints.event_data, event_controller.write_events),
    web.delete(EndPoints.event_data, event_controller.remove_events),
    # --- stream routes ---
    web.get(EndPoints.stream, stream_controller.info),
    web.put(EndPoints.stream_move, stream_controller.move),
    web.put(EndPoints.stream, stream_controller.update),
    web.post(EndPoints.stream, stream_controller.create),
    web.delete(EndPoints.stream, stream_controller.delete),
    # --- folder routes ---
    web.get(EndPoints.folders, folder_controller.index),
    web.get(EndPoints.folder, folder_controller.info),
    web.put(EndPoints.folder_move, folder_controller.move),
    web.put(EndPoints.folder, folder_controller.update),
    web.delete(EndPoints.folder, folder_controller.delete),
    # --- data routes ---
    web.get(EndPoints.data, data_controller.read),
    web.get(EndPoints.data_json, data_controller.read_json),
    web.get(EndPoints.data_intervals, data_controller.intervals),
    web.post(EndPoints.data_decimate, data_controller.decimate),
    web.delete(EndPoints.data_decimate, data_controller.drop_decimations),
    web.post(EndPoints.data_consolidate, data_controller.consolidate),
    web.post(EndPoints.data, data_controller.write),
    web.delete(EndPoints.data, data_controller.remove),
    # --- module routes ---
    web.get(EndPoints.modules, module_controller.index),
    web.get(EndPoints.module, module_controller.info),
    web.get(EndPoints.module_logs, module_controller.logs),
    # --- app routes ---
    web.get(EndPoints.app_auth, app_controller.auth),
    web.get(EndPoints.app_json, app_controller.index),

    # --- proxy routes ---
    web.get(EndPoints.proxies, proxy_controller.index),
    web.get(EndPoints.proxy, proxy_controller.info),
    # -- master routes --
    web.get(EndPoints.masters, master_controller.index),
    web.post(EndPoints.master, master_controller.add),
    web.delete(EndPoints.master, master_controller.delete),
    # -- follower routes --
    web.get(EndPoints.followers, follower_controller.index),
    web.post(EndPoints.follower, follower_controller.add),
    web.delete(EndPoints.follower, follower_controller.delete),
    # -- annotation routes --
    web.get(EndPoints.annotations_info, annotation_controller.info),
    web.get(EndPoints.annotations, annotation_controller.index),
    web.put(EndPoints.annotation, annotation_controller.update),
    web.post(EndPoints.annotation, annotation_controller.create),
    web.delete(EndPoints.annotation, annotation_controller.delete),
    web.delete(EndPoints.stream_annotations, annotation_controller.delete_all)
]

insecure_routes = [
    ['POST', EndPoints.follower]
]
