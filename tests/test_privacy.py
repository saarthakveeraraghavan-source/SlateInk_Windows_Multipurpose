from pathlib import Path
import subprocess
import sys


def test_runtime_rejects_socket_connect_and_bind():
    code = """
from slateink.privacy import enforce_offline
enforce_offline()
import socket
for operation in ['connect','bind']:
    sock = socket.socket()
    try:
        getattr(sock,operation)(('127.0.0.1',8999))
    except PermissionError:
        pass
    else:
        raise AssertionError(operation+' was not blocked')
    finally:
        sock.close()
"""
    result=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_runtime_has_no_remote_inference_or_frame_writes():
    root=Path(__file__).resolve().parent.parent/"slateink"
    text="\n".join(p.read_text(encoding="utf-8") for p in root.glob("*.py"))
    for forbidden in ("VideoWriter(","cv2.imwrite(","requests.post(","pyperclip", "trust_remote_code=True"):
        assert forbidden not in text
    assert "local_files_only=True" in text
    assert "use_safetensors=True" in text
