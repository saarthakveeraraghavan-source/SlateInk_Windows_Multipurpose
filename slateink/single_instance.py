"""One visible app/camera session per workspace and signed-in Windows user."""
import hashlib
from PySide6.QtCore import QObject,Signal,QLockFile
from PySide6.QtNetwork import QLocalServer,QLocalSocket
from .config import ROOT


class SingleInstance(QObject):
    show_requested=Signal()

    def __init__(self,name=None):
        super().__init__()
        digest=hashlib.sha256(str(ROOT.resolve()).casefold().encode()).hexdigest()[:24]
        self.name=name or "SlateInk_"+digest
        directory=ROOT/"artifacts";directory.mkdir(exist_ok=True)
        self.lock=QLockFile(str(directory/(self.name+".lock")))
        self.lock.setStaleLockTime(0)
        self.server=QLocalServer(self);self.sockets=set()
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.connected)

    def acquire(self):
        if self.lock.tryLock(0):
            if self.server.listen(self.name):return True
            self.lock.unlock()
            raise RuntimeError("Could not start SlateInk's local session service. Close old instances and reopen the app.")
        socket=QLocalSocket(self);socket.connectToServer(self.name)
        if socket.waitForConnected(1000):
            socket.write(b"show");socket.flush();socket.waitForBytesWritten(250);socket.disconnectFromServer()
            return False
        raise RuntimeError("Another SlateInk session may still be closing. Wait a moment and reopen the app.")

    def connected(self):
        while self.server.hasPendingConnections():
            socket=self.server.nextPendingConnection();self.sockets.add(socket)
            data=bytearray()
            def read(socket=socket,data=data):
                data.extend(bytes(socket.readAll()))
                if bytes(data)==b"show":self.show_requested.emit()
                if len(data)>=4:socket.disconnectFromServer()
            socket.readyRead.connect(read)
            socket.disconnected.connect(lambda socket=socket:self.sockets.discard(socket))
            if socket.bytesAvailable():read()

    def close(self):
        self.server.close();self.lock.unlock()
