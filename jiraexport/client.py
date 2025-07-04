"""Minimal Jira Cloud REST client (basic auth with an API token)."""
import logging
import os
import time

from . import __version__


class JiraError(Exception):
    def __init__(self, message, status=None, url=None):
        super().__init__(message)
        self.status = status
        self.url = url


log = logging.getLogger("jiraexport.client")


def default_session(email, token):
    import requests  # imported lazily so the tests run without it installed

    session = requests.Session()
    session.auth = (email, token)
    session.headers.update({"Accept": "application/json", "User-Agent": "jira-export/" + __version__})
    return session


# Gateway errors Atlassian returns during short outages; reads are safe to repeat.
TRANSIENT = (502, 503, 504)


def retry_after(resp, default=5):
    try:
        return max(0, int(resp.headers.get("Retry-After")))
    except (TypeError, ValueError):
        return default


class JiraClient:
    API = "/rest/api/3/"

    def __init__(self, base_url, email=None, token=None, session=None, timeout=60, max_retries=5, sleep=time.sleep):
        self.base_url = base_url.rstrip("/")
        self.session = session if session is not None else default_session(email, token)
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep = sleep

    def url(self, path):
        if path.startswith(("http://", "https://")):
            return path
        return self.base_url + self.API + path.lstrip("/")

    def _send(self, method, url, **kwargs):
        """One request, retried while Jira answers 429."""
        attempt = 0
        while True:
            log.debug("%s %s", method, url)
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            if resp.status_code == 429 and attempt < self.max_retries:
                attempt += 1
                delay = retry_after(resp)
                log.warning("rate limited; waiting %ss (retry %d of %d)", delay, attempt, self.max_retries)
                self.sleep(delay)
                continue
            if resp.status_code in TRANSIENT and method.upper() == "GET" and attempt < self.max_retries:
                attempt += 1
                delay = min(2 ** attempt, 30)
                log.warning("HTTP %s from Jira; retrying in %ss (retry %d of %d)", resp.status_code, delay, attempt, self.max_retries)
                self.sleep(delay)
                continue
            return resp

    def request(self, method, path, params=None, body=None, expected=(200,)):
        url = self.url(path)
        resp = self._send(method, url, params=params, json=body)
        if resp.status_code not in expected:
            raise JiraError("{} {} failed with HTTP {}: {}".format(method, url, resp.status_code, resp.text[:200]),
                            resp.status_code, url)
        if resp.status_code == 204 or not resp.text:
            return None
        return resp.json()

    def get(self, path, params=None):
        return self.request("GET", path, params=params)

    def download(self, path, dest, chunk_size=65536, on_chunk=None):
        """Stream a file (an attachment's content URL) to dest and return the number of bytes written.

        on_chunk, if given, sees every chunk as it is written (for checksums).
        """
        url = self.url(path)
        resp = self._send("GET", url, stream=True)
        if resp.status_code != 200:
            raise JiraError("GET {} failed with HTTP {}".format(url, resp.status_code), resp.status_code, url)
        written = 0
        partial = dest + ".part"
        try:
            with open(partial, "wb") as handle:
                for chunk in resp.iter_content(chunk_size):
                    handle.write(chunk)
                    written += len(chunk)
                    if on_chunk is not None:
                        on_chunk(chunk)
            os.replace(partial, dest)
        except BaseException:
            if os.path.exists(partial):
                os.remove(partial)
            raise
        return written
