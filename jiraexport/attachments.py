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


def download_all(client, issue_key, attachments, dest_dir, max_bytes=None):
    """Download an issue's attachments into dest_dir/<issue key>/. Returns {attachment id: note}.

    The note is the saved path, or "skipped: ..." / "failed: ..." when nothing was saved.
    """
    notes = {}
    folder = os.path.join(dest_dir, issue_key)
    for att in attachments:
        if max_bytes is not None and att.get("size", 0) > max_bytes:
            notes[att["id"]] = "skipped: larger than {} bytes".format(max_bytes)
            continue
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, local_name(att))
        if os.path.exists(target) and os.path.getsize(target) == att.get("size"):
            notes[att["id"]] = target  # fetched by an earlier run
            continue
        try:
            client.download(att["content"], target)
        except JiraError as exc:
            notes[att["id"]] = "failed: HTTP {}".format(exc.status)
            continue
        notes[att["id"]] = target
    return notes


def rows(issue_key, attachments, notes=None):
    notes = notes or {}
    return [{"issue": issue_key, "id": a["id"], "filename": a["filename"], "size": a.get("size", 0),
             "mimeType": a.get("mimeType", ""), "created": normalise_timestamp(a.get("created")),
             "author": (a.get("author") or {}).get("displayName", ""), "saved_as": notes.get(a["id"], "")}
            for a in attachments]
