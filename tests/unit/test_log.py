import json
import logging

from app.core.log import JsonFormatter, request_id

def _format(**extra) -> dict:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "note_created", None, None)
    record.__dict__.update(extra)
    return json.loads(JsonFormatter().format(record))

def test_line_has_event_level_and_extra_fields():
    line = _format(note_id="n1", author_id="a1")
    assert line["event"] == "note_created"
    assert line["level"] == "INFO"
    assert line["note_id"] == "n1" and line["author_id"] == "a1"
    assert "msg" not in line and "args" not in line

def test_line_carries_current_request_id():
    assert _format()["request_id"] == "-"
    token = request_id.set("req-123")
    try:
        assert _format()["request_id"] == "req-123"
    finally:
        request_id.reset(token)