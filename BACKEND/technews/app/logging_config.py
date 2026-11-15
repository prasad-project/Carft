import json
import logging

_STD = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        out = {"ts": self.formatTime(record), "level": record.levelname, "event": record.getMessage(), "logger": record.name}
        out.update({k: v for k, v in record.__dict__.items() if k not in _STD})
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def setup_logging():
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(logging.INFO)
