class MockSession:

    def __init__(self):
        self.path = None,
        self.data = None
        self.method = None
        self.response = None

    async def put(self,path,data):
        self.path = path
        self.data = data
        self.method = 'PUT'
        return self.response

    async def delete(self, path, data):
        self.path = path
        self.data = data
        self.method = 'DELETE'
        return self.response

    async def get(self, path, data):
        self.path = path
        self.data = data
        self.method = 'GET'
        return self.response

