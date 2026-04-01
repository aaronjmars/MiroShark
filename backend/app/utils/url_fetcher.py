"""
URL fetching and text extraction utility for MiroShark document ingestion.
Fetches a URL and extracts readable article text without extra dependencies.
"""

import re
import socket
import ipaddress
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB


class _TextExtractor(HTMLParser):
    """Simple HTML parser that strips tags and extracts readable body text."""

    # Tags whose content should be ignored entirely
    SKIP_TAGS = frozenset({
        'script', 'style', 'noscript', 'nav', 'footer', 'aside',
        'form', 'button', 'meta', 'link', 'img', 'svg', 'iframe',
        'head',
    })

    # Block-level tags that should introduce a newline when closed
    BLOCK_TAGS = frozenset({
        'p', 'div', 'article', 'section', 'main',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'li', 'br', 'tr', 'blockquote', 'pre',
    })

    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip_depth = 0
        self._title = ''
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag == 'title':
            self._in_title = True

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag == 'title':
            self._in_title = False
        if tag in self.BLOCK_TAGS:
            if self._parts and not self._parts[-1].endswith('\n'):
                self._parts.append('\n')

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self._title = text
        else:
            self._parts.append(text + ' ')

    def get_text(self) -> str:
        raw = ''.join(self._parts)
        # Normalize whitespace runs
        raw = re.sub(r'[ \t]+', ' ', raw)
        # Collapse 3+ newlines to 2
        raw = re.sub(r'\n{3,}', '\n\n', raw)
        return raw.strip()

    def get_title(self) -> str:
        return self._title.strip()


def _check_ip(ip_str: str) -> None:
    """Raises ValueError if the IP is private/loopback/reserved."""
    addr = ipaddress.ip_address(ip_str)
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        raise ValueError(
            f"Requests to private or internal addresses are not allowed ({ip_str})"
        )


def _validate_url(url: str) -> str:
    """Validate scheme/host and check resolved IP. Returns the hostname."""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(
            f"Only http and https URLs are supported (got '{parsed.scheme}')"
        )
    if not parsed.netloc:
        raise ValueError("Invalid URL: missing host")
    host = parsed.netloc.split(':')[0]
    try:
        _check_ip(socket.gethostbyname(host))
    except socket.gaierror:
        pass  # let requests surface the DNS error
    return host


def _safe_get(url: str, headers: dict, timeout: int) -> requests.Response:
    """
    GET with manual redirect following — each hop is IP-checked to prevent
    SSRF via redirect to internal addresses. Also streams the response and
    enforces a size cap so a large file can't OOM the server.
    """
    max_redirects = 5
    current_url = url

    for _ in range(max_redirects + 1):
        _validate_url(current_url)

        resp = requests.get(
            current_url, headers=headers, timeout=timeout,
            allow_redirects=False, stream=True,
        )

        if resp.is_redirect and 'location' in resp.headers:
            current_url = resp.headers['location']
            resp.close()
            continue

        resp.raise_for_status()

        # Enforce size limit while streaming
        chunks = []
        downloaded = 0
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            downloaded += len(chunk)
            if downloaded > MAX_RESPONSE_BYTES:
                resp.close()
                raise ValueError(
                    f"Response exceeds {MAX_RESPONSE_BYTES // (1024 * 1024)} MB size limit"
                )
            chunks.append(chunk)
        resp.close()

        # Reconstruct a response-like object with the full content
        resp._content = b''.join(chunks)
        return resp

    raise ValueError("Too many redirects")


def fetch_url_text(url: str, timeout: int = 15) -> dict:
    """
    Fetch a URL and extract readable text content suitable for simulation input.

    Args:
        url: The URL to fetch (must be http or https).
        timeout: Request timeout in seconds.

    Returns:
        dict with keys:
            - title (str): Page title or derived from URL
            - text (str): Extracted plain text content
            - url (str): The original URL
            - char_count (int): Length of extracted text

    Raises:
        ValueError: For invalid URLs, blocked addresses, or unextractable content.
        requests.exceptions.RequestException: For HTTP/network errors.
    """
    _validate_url(url)

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (compatible; MiroShark/1.0; '
            '+https://github.com/aaronjmars/MiroShark)'
        ),
        'Accept': 'text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    response = _safe_get(url, headers, timeout)

    parsed = urlparse(url)
    content_type = response.headers.get('content-type', '').lower()

    # Plain text or markdown
    if 'text/plain' in content_type or url.lower().endswith(('.txt', '.md')):
        text = response.text
        title = parsed.path.split('/')[-1] or parsed.netloc
        return {'title': title, 'text': text, 'url': url, 'char_count': len(text)}

    # Require HTML for everything else
    if 'text/html' not in content_type and 'application/xhtml' not in content_type:
        raise ValueError(
            f"Unsupported content type '{content_type}'. "
            "Only HTML and plain-text pages can be fetched."
        )

    parser = _TextExtractor()
    parser.feed(response.text)

    title = parser.get_title() or parsed.netloc
    text = parser.get_text()

    if len(text) < 100:
        raise ValueError(
            "Could not extract meaningful text from the page. "
            "The page may require JavaScript or have no readable content."
        )

    return {
        'title': title,
        'text': text,
        'url': url,
        'char_count': len(text),
    }
