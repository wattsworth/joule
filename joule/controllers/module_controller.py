from aiohttp import web
import aiohttp
import pdb

from joule.models import Supervisor


async def index(request):
    supervisor: Supervisor = request.app["supervisor"]
    resp = []
    for worker in supervisor.workers:
        info = {
            "id": worker.module.uuid,
            "name": worker.module.name,
            "description": worker.module.description,
            "has_interface": worker.module.has_interface,
            "inputs": {},
            "outputs": {},
            "statistics": worker.statistics()}
        for c in worker.input_connections:
            info['inputs'][c.name] = c.location
        for c in worker.output_connections:
            info['outputs'][c.name] = c.location
        resp.append(info)
    return web.json_response(data=resp)


async def info(request):
    supervisor: Supervisor = request.app["supervisor"]
    if 'name' in request.query:
        worker = [w for w in supervisor.workers if w.module.name == request.query['name']]
    else:
        return web.Response(text="specify a name", status=400)
    if len(worker) == 0:
        return web.Response(text="module does not exist", status=404)
    worker = worker[0]
    data = {
        "name": worker.module.name,
        "description": worker.module.description,
        "inputs": {},
        "outputs": {},
        "statistics": worker.statistics()}
    for c in worker.input_connections:
        data['inputs'][c.name] = c.location
    for c in worker.output_connections:
        data['outputs'][c.name] = c.location
    return web.json_response(data)


async def logs(request):
    supervisor: Supervisor = request.app["supervisor"]
    if 'name' in request.query:
        worker = [w for w in supervisor.workers if w.module.name == request.query['name']]
    else:
        return web.Response(text="specify a name", status=400)
    if len(worker) == 0:
        return web.Response(text="module does not exist", status=404)
    worker = worker[0]
    return web.json_response(worker.logs)
