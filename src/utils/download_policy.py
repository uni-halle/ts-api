"""
Restricts which URLs TsAPI downloads files from (see allowed_download_hosts).
"""
import os

from urllib3.util import parse_url
from urllib3.exceptions import LocationParseError


class DownloadNotAllowed(Exception):
    """The URL must not be downloaded."""


def allowed_download_hosts() -> list[str] | None:
    """
    The hosts from the environment variable allowed_download_hosts
    (comma separated). An entry starting with a dot also allows all
    subdomains, "*" allows every host.
    :return: The hosts, None if the variable is not set
    """
    value = os.environ.get("allowed_download_hosts", "").strip()
    if not value:
        return None
    return [host.strip().lower().rstrip(".")
            for host in value.split(",") if host.strip()]


def check_download_url(url: str) -> None:
    """
    Checks that the URL uses http(s) and points to an allowed host.
    The URL is parsed like requests/urllib3 parse it, so the checked host is
    the host that is contacted.
    :raises DownloadNotAllowed: If the URL must not be downloaded
    """
    if not url or any(char.isspace() or ord(char) < 32 or char == "\\"
                      for char in url):
        raise DownloadNotAllowed("Invalid URL")
    try:
        parsed = parse_url(url)
    except LocationParseError:
        raise DownloadNotAllowed("Invalid URL")
    if (parsed.scheme or "").lower() not in ("http", "https"):
        raise DownloadNotAllowed("Only http and https URLs are allowed")
    if parsed.auth:
        raise DownloadNotAllowed("URLs with credentials are not allowed")
    host = (parsed.host or "").lower().rstrip(".")
    if not host:
        raise DownloadNotAllowed("URL without host")

    allowed = allowed_download_hosts()
    if allowed is None:
        return
    for entry in allowed:
        if entry == "*" or host == entry \
                or (entry.startswith(".") and host.endswith(entry)):
            return
    raise DownloadNotAllowed(f"Downloads from {host} are not allowed "
                             f"(allowed_download_hosts)")
