from copy import copy


class MockSession:

    def __init__(self, multiple_calls=False):
        self.path = None,
        self.response_data = None
        self.request_data = None
        self.method = None
        self.methods = []
        self.paths = []
        self.multiple_calls = multiple_calls

    async def put(self, path, json):
        self.path = path
        self.paths.append(path)
        self._save_request_data(json)
        self.method = 'PUT'
        self.methods.append(self.method)
        return self._response_data()

    async def delete(self, path, params):
        self.path = path
        self.paths.append(path)
        self._save_request_data(params)
        self.method = 'DELETE'
        self.methods.append(self.method)
        return self._response_data()

    async def get(self, path, params):
        self.path = path
        self.paths.append(path)
        self._save_request_data(params)
        self.method = 'GET'
        self.methods.append(self.method)
        return self._response_data()

    async def post(self, path, json):
        self.path = path
        self.paths.append(path)
        self._save_request_data(json)
        self.method = 'POST'
        self.methods.append(self.method)
        return self._response_data()

    def _save_request_data(self, data):
        #print(f"data id: {id(data)}")
        if self.multiple_calls:
            if self.request_data is None:
                self.request_data = []
            self.request_data.append(copy(data))
        else:
            self.request_data = data

    def _response_data(self):
        if self.multiple_calls:
            response = self.response_data.pop(0)
        else:
            response = self.response_data
        if issubclass(type(response), Exception):
            raise response
        return response
