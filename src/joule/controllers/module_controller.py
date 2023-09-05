from aiohttp import web

from joule.models.supervisor import Supervisor


async def index(request):
    supervisor: Supervisor = request.app["supervisor"]
    resp = []
    if 'statistics' in request.query and request.query['statistics'] != '0':
        get_stats = True
    else:
        get_stats = False

    for worker in supervisor.workers:
        worker_info = {
            "id": worker.uuid,
            "name": worker.name,
            "description": worker.description,
            "is_app": worker.is_app,
            "inputs": {},
            "outputs": {}}
        if get_stats:
            worker_info['statistics'] = \
                (await worker.statistics()).to_json()

        for c in worker.input_connections:
            worker_info['inputs'][c.name] = c.location
        for c in worker.output_connections:
            worker_info['outputs'][c.name] = c.location
        resp.append(worker_info)
    return web.json_response(data=resp)


async def info(request):
    supervisor: Supervisor = request.app["supervisor"]
    if 'name' in request.query:
        worker = [w for w in supervisor.workers if w.name == request.query['name']]
    elif 'id' in request.query:
        worker = [w for w in supervisor.workers if w.uuid == int(request.query['id'])]
    else:
        return web.Response(text="specify a name or id", status=400)
    if len(worker) == 0:
        return web.Response(text="module does not exist", status=404)
    worker = worker[0]

    data = {
        "id": worker.uuid,
        "name": worker.name,
        "description": worker.description,
        "is_app": worker.is_app,
        "inputs": {},
        "outputs": {},
        "statistics": (await worker.statistics()).to_json()}
    for c in worker.input_connections:
        data['inputs'][c.name] = c.location
    for c in worker.output_connections:
        data['outputs'][c.name] = c.location
    return web.json_response(data)


async def logs(request):
    supervisor: Supervisor = request.app["supervisor"]
    if 'name' in request.query:
        worker = [w for w in supervisor.workers if w.name == request.query['name']]
    elif 'id' in request.query:
        worker = [w for w in supervisor.workers if w.uuid == int(request.query['id'])]
    else:
        return web.Response(text="specify a name", status=400)
    if len(worker) == 0:
        return web.Response(text="module does not exist", status=404)
    worker = worker[0]
    return web.json_response(worker.logs)
