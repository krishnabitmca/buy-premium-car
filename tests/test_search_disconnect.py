from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from api.search import _response


@pytest.mark.parametrize('error',[BrokenPipeError,ConnectionResetError,ConnectionAbortedError])
@pytest.mark.parametrize('stage',['headers','body'])
def test_cancelled_response_does_not_attempt_an_error_response(error,stage):
    handler=SimpleNamespace(send_response=Mock(),send_header=Mock(),
        end_headers=Mock(),wfile=SimpleNamespace(write=Mock()))
    (handler.end_headers if stage=='headers' else handler.wfile.write).side_effect=error()
    _response(handler,200,{'ok':True})
    handler.send_response.assert_called_once_with(200)
