"""Lightweight health-check endpoint for Fly's HTTP probes.

Returns 200 unconditionally — the goal is to confirm the worker process is
alive and the WSGI stack is responding, not to validate downstream services.
"""

from flask import Blueprint

healthz_bp = Blueprint("healthz", __name__)


@healthz_bp.route("/healthz")
def healthz():
    return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}
