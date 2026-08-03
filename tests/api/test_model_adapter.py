from api.contract import ModelRequest
from api.model_adapter import ModelAdapter


class FakeAdapter(ModelAdapter):
    def encode_request(self, request):
        return {"model": request.model}

    def send(self, payload):
        return payload

    def decode_response(self, raw_response):
        return raw_response


def test_complete_runs_the_three_steps():
    adapter = FakeAdapter()
    request = ModelRequest(
        model="test-model",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert adapter.complete(request) == {"model": "test-model"}
