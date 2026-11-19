# web_server.py
# Minimal non-blocking HTTP server.
#   GET  /      -> index.html (streamed from flash, not held in RAM)
#   POST /api   -> JSON command, passed to CommandHandler
# poll() handles at most one waiting client and returns immediately when
# nobody is connected, so the main loop can keep the face and touch sensor
# running.

import json
import os
import socket

import config
from logger import log, error


class WebServer:

    def __init__(self, commands):
        self.commands = commands
        self.sock = None

    def start(self, ip):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", config.HTTP_PORT))
        self.sock.listen(2)
        self.sock.setblocking(False)
        log("HTTP SERVER READY  ->  http://" + ip)

    # ------------------------------------------------------------------
    def poll(self):
        try:
            client, addr = self.sock.accept()
        except OSError:
            return                      # nobody waiting

        try:
            client.settimeout(3)
            self._handle(client)
        except Exception as e:
            error("Server error: " + str(e))
        finally:
            try:
                client.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _handle(self, client):
        request = self._read_request(client)
        if request is None:
            return
        method, path, body = request
        path = path.split("?")[0]

        if method == "GET" and path in ("/", "/index.html"):
            self._send_file(client, config.HTML_FILE)

        elif method == "POST" and path == "/api":
            try:
                command = json.loads(body)
            except Exception:
                self._send(client, "400 Bad Request", "application/json",
                           json.dumps({"status": "error", "message": "Invalid JSON"}))
                return
            result = self.commands.process(command)
            self._send(client, "200 OK", "application/json", json.dumps(result))

        else:
            self._send(client, "404 Not Found", "text/plain", "Not found")

    # ------------------------------------------------------------------
    @staticmethod
    def _read_request(client):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = client.recv(512)
            if not chunk:
                break
            data += chunk
            if len(data) > 8192:
                break

        end = data.find(b"\r\n\r\n")
        if end == -1:
            return None

        head = data[:end].decode()
        body = data[end + 4:]
        lines = head.split("\r\n")

        length = 0
        for line in lines[1:]:
            if line.lower().startswith("content-length:"):
                length = int(line.split(":", 1)[1].strip())

        while len(body) < length:
            chunk = client.recv(min(512, length - len(body)))
            if not chunk:
                break
            body += chunk

        parts = lines[0].split(" ")
        if len(parts) < 2:
            return None
        return parts[0], parts[1], body.decode()

    # ------------------------------------------------------------------
    @staticmethod
    def _write(client, data):
        sent = 0
        while sent < len(data):
            sent += client.send(data[sent:])

    def _send(self, client, status, content_type, data):
        if isinstance(data, str):
            data = data.encode()
        header = ("HTTP/1.1 " + status + "\r\n"
                  "Content-Type: " + content_type + "\r\n"
                  "Content-Length: " + str(len(data)) + "\r\n"
                  "Connection: close\r\n\r\n")
        self._write(client, header.encode())
        self._write(client, data)

    def _send_file(self, client, filename):
        try:
            size = os.stat(filename)[6]
            f = open(filename, "rb")
        except OSError:
            self._send(client, "404 Not Found", "text/plain", filename + " not found")
            return
        try:
            header = ("HTTP/1.1 200 OK\r\n"
                      "Content-Type: text/html\r\n"
                      "Content-Length: " + str(size) + "\r\n"
                      "Connection: close\r\n\r\n")
            self._write(client, header.encode())
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                self._write(client, chunk)
        finally:
            f.close()
