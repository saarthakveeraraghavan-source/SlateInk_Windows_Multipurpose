"""Runtime policy: no downloads, telemetry, listeners, or outbound Python sockets."""
import os
import sys


def enforce_offline():
    for key, value in {
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
        "TOKENIZERS_PARALLELISM": "false",
    }.items():
        os.environ[key] = value

    def audit(event, args):
        if event in {"socket.connect", "socket.connect_ex", "socket.bind", "socket.getaddrinfo"}:
            raise PermissionError("SlateInk runtime has no network access. Use setup_models.py separately.")
    sys.addaudithook(audit)
