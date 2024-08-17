"""Attachment metadata and optional downloads."""
import os

from .client import JiraError
from .flatten import normalise_timestamp

COLUMNS = ("issue", "id", "filename", "size", "mimeType", "created", "author", "saved_as")


def safe_filename(name):
    """A name that cannot escape the target folder: no directories, no control characters."""
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch if ch.isprintable() else "_" for ch in name).strip(" .")
    return name or "attachment"


def local_name(attachment):
    # The id keeps two attachments with the same filename apart.
    return "{}-{}".format(attachment["id"], safe_filename(attachment["filename"]))


def _fetch_one(client, att, folder, max_bytes):
    """Note for one attachment: its saved path, or 'skipped: ...' / 'failed: ...'."""
    if max_bytes is not None and att.get("size", 0) > max_bytes:
        return "skipped: larger than {} bytes".format(max_bytes)
    target = os.path.join(folder, local_name(att))
    if os.path.exists(target) and os.path.getsize(target) == att.get("size"):
        return target  # fetched by an earlier run
    try:
        client.download(att["content"], target)
    except JiraError as exc:
        return "failed: HTTP {}".format(exc.status)
    return target


def download_all(client, issue_key, attachments, dest_dir, max_bytes=None, workers=1):
    """Download an issue's attachments into dest_dir/<issue key>/. Returns {attachment id: note}.

    The note is the saved path, or "skipped: ..." / "failed: ..." when nothing was saved.
    With workers > 1 the files of one issue are fetched concurrently.
    """
    folder = os.path.join(dest_dir, issue_key)
    if attachments:
        os.makedirs(folder, exist_ok=True)
    if workers > 1 and len(attachments) > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=min(workers, len(attachments))) as pool:
            results = list(pool.map(lambda att: _fetch_one(client, att, folder, max_bytes), attachments))
    else:
        results = [_fetch_one(client, att, folder, max_bytes) for att in attachments]
    return {att["id"]: note for att, note in zip(attachments, results)}


def rows(issue_key, attachments, notes=None):
    notes = notes or {}
    return [{"issue": issue_key, "id": a["id"], "filename": a["filename"], "size": a.get("size", 0),
             "mimeType": a.get("mimeType", ""), "created": normalise_timestamp(a.get("created")),
             "author": (a.get("author") or {}).get("displayName", ""), "saved_as": notes.get(a["id"], "")}
            for a in attachments]
