import os
import time
import struct
import math
import random
import win32api
import win32gui
import win32process
from ctypes  import *
from pymem   import *
import numpy as np
import requests

from http.server import BaseHTTPRequestHandler, HTTPServer
import sys
import json

ReadProcessMemory = windll.kernel32.ReadProcessMemory
WriteProcessMemory = windll.kernel32.WriteProcessMemory

# stuff for RAM...
def update_offsets(raw):
    raw = raw.replace('[signatures]','#signatures\n')
    raw = raw.replace('[netvars]','#netvars\n')
    try:
        open('dm_hazedumper_offsets.py','w').write(raw)
        print('updated succesfuly')
    except:
        print('couldnt open offsets.py to preform update')
    return

def getlength(type):
    # integer float char ? require diff lengths
    if type == 'i':
        return 4
    elif type == 'f':
        return 4
    elif type == 'c':
        return 1
    elif type == 'b': #tp added
        return 1 # maybe 4
    elif type == 'h': #tp added
        return 4

def read_memory(game, address, type):
    # buffer = (ctypes.c_byte * getlength(type))()
    buffer = c_int(0)
    # bytesRead = ctypes.c_ulonglong(0)
    bytesRead = c_ulong(0)
    # readlength = getlength(type)
    readlength = sizeof(c_int)
    address_ptr = c_void_p(address)

    # ReadProcessMemory(game, address, buffer, readlength, byref(bytesRead))
    ReadProcessMemory(game, address_ptr, byref(buffer), readlength, byref(bytesRead))
    # return struct.unpack(type, buffer)[0]
    return buffer.value

# stuff for game state integration...

import selectors
if hasattr(selectors, 'PollSelector'):
    _ServerSelector = selectors.PollSelector
else:
    _ServerSelector = selectors.SelectSelector


# https://docs.python.org/2/library/basehttpserver.html
# info about HTTPServer, BaseHTTPRequestHandler
class MyServer(HTTPServer):
    def __init__(self, server_address, token, RequestHandler):
        self.auth_token = token
        super(MyServer, self).__init__(server_address, RequestHandler)
        # create all the states of interest here
        self.data_all = None
        # my_dict = {1: 'apple', 2: 'ball'}
        self.round_phase = None
        self.player_status = None

    def serve_forever(self, poll_interval=0.5):
        """Handle one request at a time until shutdown.

        Polls for shutdown every poll_interval seconds. Ignores
        self.timeout. If you need to do periodic tasks, do them in
        another thread.
        """
        self.__is_shut_down.clear()
        try:
            # XXX: Consider using another file descriptor or connecting to the
            # socket to wake this up instead of polling. Polling reduces our
            # responsiveness to a shutdown request and wastes cpu at all other
            # times.
            with _ServerSelector() as selector:
                selector.register(self, selectors.EVENT_READ)

                while not self.__shutdown_request:
                    ready = selector.select(poll_interval)
                    # bpo-35017: shutdown() called during select(), exit immediately.
                    if self.__shutdown_request:
                        break
                    if ready:
                        self._handle_request_noblock()

                    self.service_actions()
        finally:
            self.__shutdown_request = False
            self.__is_shut_down.set()

    def handle_request(self):
        """Handle one request, possibly blocking.

        Respects self.timeout.
        """
        # Support people who used socket.settimeout() to escape
        # handle_request before self.timeout was available.
        timeout = self.socket.gettimeout()
        if timeout is None:
            timeout = self.timeout
        elif self.timeout is not None:
            timeout = min(timeout, self.timeout)
        if timeout is not None:
            deadline = time() + timeout

        # Wait until a request arrives or the timeout expires - the loop is
        # necessary to accommodate early wakeups due to EINTR.
        with _ServerSelector() as selector:
            selector.register(self, selectors.EVENT_READ)

            while True:
                ready = selector.select(timeout)
                if ready:
                    return self._handle_request_noblock()
                else:
                    if timeout is not None:
                        timeout = deadline - time()
                        if timeout < 0:
                            return self.handle_timeout()

    def _handle_request_noblock(self):
        """Handle one request, without blocking.

        I assume that selector.select() has returned that the socket is
        readable before this function was called, so there should be no risk of
        blocking in get_request().
        """
        try:
            request, client_address = self.get_request()
        except OSError:
            return
        if self.verify_request(request, client_address):
            try:
                return self.process_request(request, client_address)
            except Exception:
                self.handle_error(request, client_address)
                self.shutdown_request(request)
                return
            except:
                self.shutdown_request(request)
                raise
            return
        else:
            self.shutdown_request(request)
            return

    def process_request(self, request, client_address):
        """Call finish_request.

        Overridden by ForkingMixIn and ThreadingMixIn.

        """
        finish_request_res = self.finish_request(request, client_address)
        self.shutdown_request(request)

        return finish_request_res

    def finish_request(self, request, client_address):
        """Finish one request by instantiating RequestHandlerClass."""
        return self.RequestHandlerClass(request, client_address, self)

# need this running in the background
class MyRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = self.rfile.read(length).decode('utf-8')


        # # # 打印n
        payload = json.loads(body)
        self.parse_payload(payload)

        self.send_header('Content-type', 'text/html')
        self.send_response(200)
        self.end_headers()

    def is_payload_authentic(self, payload):
        if 'auth' in payload and 'token' in payload['auth']:
            return payload['auth']['token'] == server.auth_token
        else:
            return False

    def parse_payload(self, payload):
        # Ignore unauthenticated payloads
        # if not self.is_payload_authentic(payload):
        #     return None

        # print(payload)n
        self.server.data_all = payload.copy()


        if False:
            print('\n')
            for key in payload:
                print(key,payload[key])
            time.sleep(2)

        # self.timeout = payload['timeout']

        round_phase = self.get_round_phase(payload)

        # could only print when change phase
        if round_phase != self.server.round_phase:
            self.server.round_phase = round_phase

        # get player status - health, armor, kills this round, etc.
        player_status = self.get_player_status(payload)

    def get_round_phase(self, payload):
        if 'round' in payload and 'phase' in payload['round']:
            return payload['round']['phase']
        else:
            return None

    def get_player_status(self, payload):
        if 'player_state' in payload:
            return payload['player_state']
        else:
            return None

    def log_message(self, format, *args):
        """
        Prevents requests from printing into the console
        """
        return


assert 1==1, "这里需要在steam的csgo路径下更新 TOKEN配置文件，参考链接如下： https://www.reddit.com/r/GlobalOffensive/comments/cjhcpy/game_state_integration_a_very_large_and_indepth/"
server = MyServer(('localhost', 3000), 'AAAAA', MyRequestHandler)
# while True:
#     server.handle_request()
# server.serve_forever()
print(f'server listening at http://localhost:3000, with token {server.auth_token}')

