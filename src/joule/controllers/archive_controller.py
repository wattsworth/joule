from aiohttp import web
import os
from datetime import datetime
from joule.utilities import archive_tools
from joule import app_keys


async def add(request: web.Request):
    importer_manager = request.app[app_keys.importer_manager]
    target_file = os.path.join(request.app[app_keys.uploaded_archives_dir],
                               datetime.now().strftime('%Y%m%d%H%M%S%f.zip'))
    with open(target_file,'wb') as f:
        async for data in request.content.iter_any():
            f.write(data)
    # make sure the uploaded file looks like a joule archive
    try:
        metadata = archive_tools.read_metadata(target_file)
    except ValueError:
        os.remove(target_file)
        raise web.HTTPBadRequest(reason="invalid joule archive")
    logger: archive_tools.ImportLogger = await importer_manager.process_archive(metadata=metadata, archive_path=target_file)
    # list of level,message where level is error|warning|info
    return web.json_response(logger.to_json())
        