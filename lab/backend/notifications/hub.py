from __future__ import annotations

import base64
import hashlib
import json
import queue
import socket
import struct
import threading
from typing import Any


class EventHub:
    def __init__(self) -> None:
        self._sse_clients: set[queue.Queue[dict[str, Any]]] = set()
        self._ws_clients: set[socket.socket] = set()
        self._lock = threading.Lock()

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, "payload": payload}
        with self._lock:
            sse_clients = list(self._sse_clients)
            ws_clients = list(self._ws_clients)
        for client in sse_clients:
            try:
                client.put_nowait(event)
            except queue.Full:
                self.remove_sse(client)
        encoded = self._ws_frame(json.dumps(event).encode("utf-8"))
        for ws in ws_clients:
            try:
                ws.sendall(encoded)
            except OSError:
                self.remove_ws(ws)

    def add_sse(self) -> queue.Queue[dict[str, Any]]:
        client: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=100)
        with self._lock:
            self._sse_clients.add(client)
        return client

    def remove_sse(self, client: queue.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._sse_clients.discard(client)

    def websocket_accept(self, key: str) -> str:
        token = (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
        return base64.b64encode(hashlib.sha1(token).digest()).decode("ascii")

    def add_ws(self, ws: socket.socket) -> None:
        with self._lock:
            self._ws_clients.add(ws)

    def remove_ws(self, ws: socket.socket) -> None:
        with self._lock:
            self._ws_clients.discard(ws)
        try:
            ws.close()
        except OSError:
            pass

    def _ws_frame(self, payload: bytes) -> bytes:
        length = len(payload)
        if length < 126:
            return bytes([0x81, length]) + payload
        if length < 65536:
            return bytes([0x81, 126]) + struct.pack("!H", length) + payload
        return bytes([0x81, 127]) + struct.pack("!Q", length) + payload
