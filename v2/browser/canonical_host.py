"""301-redirect any request whose Host header doesn't match CANONICAL_HOST.

Used to force all traffic onto the custom domain (e.g. app.nhldata.org) so the
default Fly.io hostname (nhl-browser.fly.dev) becomes a redirect target rather
than a parallel entry point. /healthz is exempt because Fly's internal probes
hit the machine via the .fly.dev hostname.
"""

import os

from flask import Flask, redirect, request


def install(server: Flask) -> None:
    canonical = os.environ.get("CANONICAL_HOST")
    if not canonical:
        return

    @server.before_request
    def _enforce_canonical_host():
        if request.path == "/healthz":
            return None
        host = request.host.split(":")[0]
        if host == canonical:
            return None
        target = f"https://{canonical}{request.path}"
        if request.query_string:
            target += "?" + request.query_string.decode()
        return redirect(target, code=301)
