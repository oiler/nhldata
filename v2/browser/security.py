"""Security header configuration for the deployed Dash app.

Fly.io's edge handles TLS, HSTS preload, and HTTP→HTTPS redirects. Talisman
fills in the headers a reverse proxy would otherwise add. Dash requires
'unsafe-inline' and 'unsafe-eval' in script-src — tightening past that
requires custom Dash setup with nonces and isn't worth it here.
"""

from flask import Flask
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix

_CSP = {
    "default-src": "'self'",
    "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:"],
    "font-src": ["'self'", "data:"],
    "connect-src": "'self'",
    "frame-ancestors": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
}

_PERMISSIONS_POLICY = {
    "camera": "()",
    "microphone": "()",
    "geolocation": "()",
}


def install(server: Flask) -> None:
    # Trust the X-Forwarded-Proto / X-Forwarded-For headers Fly's edge sets.
    # Without this, request.is_secure stays False behind the proxy and HSTS won't fire.
    server.wsgi_app = ProxyFix(server.wsgi_app, x_for=1, x_proto=1, x_host=1)

    Talisman(
        server,
        content_security_policy=_CSP,
        content_security_policy_nonce_in=[],
        force_https=False,  # Fly's edge already redirects HTTP -> HTTPS
        strict_transport_security=True,
        strict_transport_security_max_age=63072000,
        strict_transport_security_include_subdomains=True,
        referrer_policy="strict-origin-when-cross-origin",
        frame_options="DENY",
        permissions_policy=_PERMISSIONS_POLICY,
        x_content_type_options=True,
    )
