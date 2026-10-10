"""Ordered, persistent uplink queue. If the link fails, packets wait on disk and go out in order."""
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

log = logging.getLogger("fireline.uplink")


class Uplink:
    def __init__(self, base_url: str, queue_file: str = "uplink_queue.jsonl"):
        self.url = base_url.rstrip("/") + "/api/uplink"
        self.base_url = base_url.rstrip("/")
        self.queue_file = Path(queue_file)
        self.q: deque[bytes] = deque()
        self.lock = threading.Lock()
        if self.queue_file.exists():
            self.q.extend(line.encode() for line in self.queue_file.read_text().splitlines() if line.strip())
            log.info("restored %d queued packets", len(self.q))
        threading.Thread(target=self._loop, daemon=True).start()

    def send(self, packet: bytes) -> None:
        with self.lock:
            self.q.append(packet)
            self._persist()

    def _persist(self) -> None:
        self.queue_file.write_text("\n".join(p.decode() for p in self.q))

    def _loop(self) -> None:
        backoff = 1.0
        while True:
            with self.lock:
                head = self.q[0] if self.q else None
            if head is None:
                time.sleep(0.2)
                continue
            status, body = self._post(head)
            if status == 202 or status in (413, 422):
                # 413/422 will never succeed; log and drop so they do not block the queue.
                if status != 202:
                    log.error("server refused packet (%s): %s", status, body)
                with self.lock:
                    self.q.popleft()
                    self._persist()
                backoff = 1.0
            else:
                log.warning("uplink failed (%s %s); retrying in %.0fs", status, body[:80], backoff)
                time.sleep(backoff)
                backoff = min(30.0, backoff * 2)

    def _post(self, packet: bytes) -> tuple[int, str]:
        req = urllib.request.Request(self.url, data=packet, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
        except (urllib.error.URLError, OSError) as e:
            return 0, str(e)

    def snapshot(self, unit_id: str, jpeg: bytes) -> None:
        """Side channel, best effort: crops are too big for the satellite."""
        req = urllib.request.Request(f"{self.base_url}/api/units/{unit_id}/snapshot", data=jpeg, method="POST",
                                     headers={"Content-Type": "image/jpeg"})
        try:
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:
            log.warning("snapshot upload failed: %s", e)
