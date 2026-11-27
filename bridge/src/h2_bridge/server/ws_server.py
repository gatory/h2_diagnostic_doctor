"""WebSocketServer: sends the newest message to every connected browser, from its own thread.

    with WebSocketServer(host="0.0.0.0", port=8765) as server:   # listening once this returns
        server.publish(text)                                     # from any thread; never blocks

The poll loop stays an ordinary blocking loop in the main thread (it owns Ctrl-C:
Python only lets the main thread set signal handlers). The asyncio side lives in
a background thread with its own event loop; publish() hands each message across
with call_soon_threadsafe.

Newest wins: each client gets the latest message when it's ready for one, never
a queue. A slow client (or a slow network) skips messages instead of falling
further and further behind, and a client that connects late gets the newest one
at once.
"""

import asyncio
import threading

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

# Biggest message a client may send. Clients send nothing for now; this keeps a stray one small.
MAX_INCOMING = 2**16


class WebSocketServer:
    """A WebSocket server in a background thread that broadcasts the newest published message.

    Attributes
    ----------
    port : int
        The port it listens on (the real one, if it was started with port 0).
    clients : int
        How many browsers are connected right now.
    """

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.clients = 0
        self._latest = None  # the newest published message (str), read only on the loop's thread
        self._wakeups = set()  # one asyncio.Event per connected client: "there's a newer message"
        self._loop = None
        self._thread = None
        self._stop = None  # asyncio.Future: done -> the server shuts down
        self._ready = threading.Event()
        self._error = None  # what went wrong starting up (port in use...), re-raised by start()

    # ------------------------------------------------------------ Main thread

    def start(self):
        """Start listening; returns once it is (or raises OSError, e.g. the port is in use)."""
        if self._thread is not None:
            return self
        self._thread = threading.Thread(target=self._run, name="ws-server", daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._error is not None:
            self._thread.join()
            raise self._error
        return self

    def publish(self, text):
        """Make `text` the newest message; each client gets it when it's ready. Safe from any thread."""
        if self._loop is not None and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(self._set_latest, text)
            except RuntimeError:  # the loop closed in between: we're shutting down
                pass

    def close(self):
        """Disconnect every client and stop the thread. Safe to call twice."""
        if self._thread is None:
            return
        if self._loop is not None and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(self._stop.set_result, None)
            except RuntimeError:
                pass
        self._thread.join(timeout=5)
        self._thread = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc_info):
        self.close()

    # ------------------------------------------------------------ The server's thread

    def _run(self):
        self._loop = asyncio.new_event_loop()
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as e:  # can't listen: hand it to start()
            self._error = e
        finally:
            self._ready.set()  # also on failure, so start() never hangs
            self._loop.close()

    async def _serve(self):
        self._stop = self._loop.create_future()
        async with serve(self._handle, self.host, self.port, max_size=MAX_INCOMING) as server:
            self.port = server.sockets[0].getsockname()[1]
            self._ready.set()
            await self._stop
        # Leaving `async with` closes every connection (close code 1001, going away).

    def _set_latest(self, text):
        self._latest = text
        for wakeup in self._wakeups:
            wakeup.set()

    async def _handle(self, connection):
        """One client: send it the newest message whenever there's a newer one, until it leaves."""
        wakeup = asyncio.Event()
        if self._latest is not None:
            wakeup.set()  # a late joiner gets the newest message at once
        self._wakeups.add(wakeup)
        self.clients += 1
        sender = asyncio.ensure_future(self._send_newest(connection, wakeup))
        reader = asyncio.ensure_future(self._ignore_incoming(connection))
        try:
            await asyncio.wait({sender, reader}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            sender.cancel()
            reader.cancel()
            self._wakeups.discard(wakeup)
            self.clients -= 1
            if not self.clients:
                self._latest = None  # nothing is published with no one listening: it would go stale

    async def _send_newest(self, connection, wakeup):
        try:
            while True:
                await wakeup.wait()
                wakeup.clear()
                await connection.send(self._latest)  # waits while the client is slow; newer ones replace it meanwhile
        except ConnectionClosed:
            pass

    async def _ignore_incoming(self, connection):
        """Read (and drop) whatever the client sends, so it never piles up; ends when the client leaves."""
        try:
            async for _ in connection:
                pass
        except ConnectionClosed:
            pass
