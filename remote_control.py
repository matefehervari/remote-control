#!/bin/env python3
import base64
import logging
import os
import signal
import subprocess
import sys
import threading
import traceback
import webbrowser
from dataclasses import asdict, dataclass
from io import BytesIO
from time import sleep
from types import SimpleNamespace
from typing import Callable

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request
from flask_cors import CORS
from PIL import Image
from werkzeug.serving import make_server

from capturing import Capturing

platform = os.name

if platform == "nt":
    import win32clipboard as clp
    import keyboard
    import ctypes

    def stop_start():
        keyboard.send("play/pause media")

    def suspend():
        ctypes.windll.powrprof.SetSuspendState(False, True, False)

else:
    clp = SimpleNamespace()

    def stop_start():
        subprocess.run(["playerctl", "play-pause"])

    def suspend():
        subprocess.run(
            ["bash", "-c", "echo mem | sudo tee /sys/power/state 1>/dev/null"]
        )

    def shutdown():
        subprocess.run(["poweroff"])


load_dotenv()

HOST = os.getenv("RC_HOST")
PORT = os.getenv("RC_PORT")
API_KEY = os.getenv("API_KEY")

if HOST is None:
    sys.stderr.write("No HOST address found in .env")
    exit(1)

if PORT is None:
    sys.stderr.write("No PORT address found in .env")
    exit(1)

if API_KEY is None:
    sys.stderr.write("No API key found in .env")
    exit(1)

if not PORT.isnumeric():
    sys.stderr.write(f"Invalid PORT {PORT} given in .env")
    exit(1)

PORT = int(PORT)


@dataclass
class Request:
    action: str
    payload: str

    def __str__(self):
        return str(asdict(self))


if platform == "nt":

    def copy_image_to_clipboard(image: Image.Image):
        output = BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # strip BMP header for clipboard
        output.close()

        clp.OpenClipboard()
        clp.EmptyClipboard()
        clp.SetClipboardData(clp.CF_DIB, data)
        clp.CloseClipboard()


class CustomLogHandler(logging.Handler):
    def __init__(self, log_callback):
        super().__init__()
        self.log = log_callback

    def emit(self, record):
        log_entry = self.format(record)
        self.log(log_entry)


class RemoteControlThread(threading.Thread):
    def __init__(self, host=HOST, port=PORT, log: Callable[..., None] = print):
        threading.Thread.__init__(self)
        self.daemon = True  # Thread will shut down with main program
        self.log = log

        self.log_handler = CustomLogHandler(self.log)
        self.log_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

        # Create Flask App
        self.app = Flask("Remote control")
        CORS(self.app)
        self.setup_routes()

        # Attach the handler to Flask's logger
        self.app.logger.addHandler(self.log_handler)

        # Lower Flask's built-in logging level
        self.app.logger.setLevel(logging.INFO)

        ssl_context = ("certs/server.crt", "certs/server.key")
        self.server = make_server(host, port, self.app, ssl_context=ssl_context)
        self.ctx = self.app.app_context()

    def setup_routes(self):
        @self.app.before_request
        def check_api_key():
            if request.endpoint != "health_check":
                key = request.headers.get("X-API-Key")
                if key != API_KEY:
                    self.log("[Auth] Received unauthorised request")
                    abort(401)

        @self.app.route("/", methods=["POST"])
        def handle_request():
            try:
                json = request.get_json()
                req = Request(**json)

                if req.payload.startswith("data:image/png;base64,"):
                    self.log("[Request] Detected base64 PNG. Copying to clipboard...")
                    base64_data = req.payload.split(",", 1)[1]
                    image_data = base64.b64decode(base64_data)
                    image = Image.open(BytesIO(image_data))

                    if platform == "nt":
                        copy_image_to_clipboard(image)
                        return jsonify({"status": "image copied to clipboard"}), 200
                    elif platform == "posix":
                        return jsonify({"status": "image copy not yet supported"}), 200

                match req.action:
                    case "open-browser":
                        webbrowser.open_new_tab(req.payload)
                        self.log(
                            f"[Request] Processed action: {req.action} to URL {req.payload}"
                        )
                        return jsonify({"status": "browser opened"}), 200

                return jsonify({"error": "unkown action"}), 400
            except Exception as e:
                self.log("[Error]", e)
                return jsonify({"error": str(e)}), 500

        @self.app.route("/stop_start", methods=["POST"])
        def handle_stop_start():
            self.log("[Request] Stop-Start received")
            stop_start()
            return jsonify({"status": "stop_start executed"}), 200

        @self.app.route("/suspend", methods=["POST"])
        def handle_suspend():
            self.log("[Request] Suspend received")

            delay_thread_start(1, suspend)
            return jsonify({"status": "suspend executed"}), 200

        @self.app.route("/shutdown", methods=["POST"])
        def handle_shutdown():
            self.log("[Request] Shutdown received")

            delay_thread_start(1, shutdown)
            return jsonify({"status": "suspend executed"}), 200

    def run(self):
        try:
            self.log("Flask server starting...")
            self.ctx.push()
            with Capturing() as output:
                self.server.log_startup()
            for line in output:
                self.log(line)
            self.server.serve_forever()
        except Exception as e:
            self.log(
                "[Error] ", traceback.format_exception(type(e), e, e.__traceback__)
            )

    def shutdown(self):
        self.log("Flask server stopping...")
        self.server.shutdown()


def delay_thread_start(delay, target):
    def wrapper():
        sleep(delay)
        target()

    threading.Thread(target=wrapper).start()


def main():
    print("Creating threads...")
    flask_thread = RemoteControlThread()
    flask_thread.start()

    def signal_handler(*_):
        print("Caught signal, shutting down...")
        flask_thread.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)


if __name__ == "__main__":
    main()
