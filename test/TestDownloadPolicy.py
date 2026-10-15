import pytest

from utils.download_policy import (DownloadNotAllowed, allowed_download_hosts,
                                   check_download_url)


class TestDownloadPolicy:

    def test_not_configured_allows_every_http_host(self, monkeypatch):
        monkeypatch.delenv("allowed_download_hosts", raising=False)
        assert allowed_download_hosts() is None
        check_download_url("https://any.example.org/a.mp4")
        check_download_url("http://10.0.0.1:8080/a.mp4")

    @pytest.mark.parametrize("url", [
        "ftp://opencast.example.org/a.mp4",
        "file:///etc/passwd",
        "gopher://opencast.example.org/",
        "opencast.example.org/a.mp4",
        "https:///a.mp4",
        "https://user:pw@opencast.example.org/a.mp4",
        "https://opencast.example.org\\@evil.example.com/",
        "https://opencast.example.org/a b.mp4",
        "",
    ])
    def test_invalid_urls(self, url, monkeypatch):
        monkeypatch.delenv("allowed_download_hosts", raising=False)
        with pytest.raises(DownloadNotAllowed):
            check_download_url(url)

    @pytest.mark.parametrize("url", [
        "https://opencast.example.org/a.mp4",
        "http://OpenCast.Example.org:8080/a.mp4",
        "https://opencast.example.org./a.mp4",
        "https://media.uni.example/a.mp4",
        "https://cdn.media.uni.example/a.mp4",
    ])
    def test_allowed_hosts(self, url, monkeypatch):
        monkeypatch.setenv("allowed_download_hosts",
                           "opencast.example.org, .media.uni.example,"
                           "media.uni.example")
        check_download_url(url)

    @pytest.mark.parametrize("url", [
        "https://evil.example.org/a.mp4",
        "https://opencast.example.org.evil.com/a.mp4",
        "https://xopencast.example.org/a.mp4",
        "https://evil.com/?https://opencast.example.org/",
        "https://evil.com#@opencast.example.org/",
        "http://127.0.0.1/a.mp4",
        "https://uni.example/a.mp4",
    ])
    def test_forbidden_hosts(self, url, monkeypatch):
        monkeypatch.setenv("allowed_download_hosts",
                           "opencast.example.org,.media.uni.example")
        with pytest.raises(DownloadNotAllowed):
            check_download_url(url)

    def test_wildcard(self, monkeypatch):
        monkeypatch.setenv("allowed_download_hosts", "*")
        check_download_url("https://anything.example.com/")
        with pytest.raises(DownloadNotAllowed):
            check_download_url("ftp://anything.example.com/")
