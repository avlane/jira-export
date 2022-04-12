"""Minimal Jira Cloud REST client (basic auth with an API token)."""
import time


class JiraError(Exception):
    def __init__(self, message, status=None, url=None):
        super().__init__(message)
        self.status = status
        self.url = url


def default_session(email, token):
    import requests  # imported lazily so the tests run without it installed

    session = requests.Session()
    session.auth = (email, token)
    session.headers.update({"Accept": "application/json", "User-Agent": "jira-export/0.1"})
    return session


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
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            if resp.status_code == 429 and attempt < self.max_retries:
                attempt += 1
                self.sleep(retry_after(resp))
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

    def download(self, path, dest, chunk_size=65536):
        """Stream a file (an attachment's content URL) to dest and return the number of bytes written."""
        url = self.url(path)
        resp = self._send("GET", url, stream=True)
        if resp.status_code != 200:
            raise JiraError("GET {} failed with HTTP {}".format(url, resp.status_code), resp.status_code, url)
        written = 0
        with open(dest, "wb") as handle:
            for chunk in resp.iter_content(chunk_size):
                handle.write(chunk)
                written += len(chunk)
        return written
