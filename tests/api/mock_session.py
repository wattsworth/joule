class MockSession:

    def __init__(self):
        self.path = None,
        self.response_data = None
        self.request_data = None
        self.method = None

    async def put(self, path, json):
        self.path = path
        self.request_data = json
        self.method = 'PUT'
        return self.response_data

    async def delete(self, path, params):
        self.path = path
        self.request_data = params
        self.method = 'DELETE'
        return self.response_data

    async def get(self, path, params):
        self.path = path
        self.request_data = params
        self.method = 'GET'
        return self.response_data

    async def post(self, path, json):
        self.path = path
        self.request_data = json
        self.method = 'POST'
        return self.response_data
