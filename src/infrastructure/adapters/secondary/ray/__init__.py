"""Ray adapter package - pre-initializes Ray connection.

If the Ray cluster is unreachable, the package still loads successfully
but marks Ray as unavailable. Callers should use client.is_ray_available()
to check before making Ray calls.
"""

from __future__ import annotations

import logging
import os
import socket

logger = logging.getLogger(__name__)

# Set environment variables BEFORE any Ray import
os.environ.setdefault("RAY_ADDRESS", "ray://localhost:10001")
os.environ.setdefault("RAY_NAMESPACE", "memstack")

# Timeout in seconds for initial Ray cluster connectivity check
_RAY_CONNECT_TIMEOUT = int(os.environ.get("RAY_CONNECT_TIMEOUT", "3"))

_ray_init_failed = False


def _check_ray_reachable(address: str, timeout: int = 3) -> bool:
    """Quick TCP check to see if Ray head node is reachable."""
    # Parse host:port from "ray://host:port"
    addr = address.replace("ray://", "")
    if ":" in addr:
        host, port_str = addr.rsplit(":", 1)
        port = int(port_str)
    else:
        host, port = addr, 10001

    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (TimeoutError, OSError):
        return False


# Disable Ray's auto_init to prevent uncontrolled ray.init() calls.
# All initialization goes through the module-level code below or
# client.init_ray_if_needed().
import ray._private.auto_init_hook as _auto_init_hook

_auto_init_hook.enable_auto_connect = False

# Now safe to import ray
import ray as _ray

# Try to initialize Ray; pre-check TCP connectivity to fail fast
if not _ray.is_initialized():
    _ray_address = os.environ.get("RAY_ADDRESS", "ray://localhost:10001")
    if not _check_ray_reachable(_ray_address, timeout=_RAY_CONNECT_TIMEOUT):
        _ray_init_failed = True
        logger.warning(
            "[Ray] Cluster at %s is unreachable (TCP check failed after %ds). "
            "Ray features disabled.",
            _ray_address,
            _RAY_CONNECT_TIMEOUT,
        )
    else:
        try:
            _ray.init(
                address=_ray_address,
                namespace=os.environ.get("RAY_NAMESPACE", "memstack"),
                ignore_reinit_error=True,
                log_to_driver=False,
            )
        except ValueError as e:
            if "already connected" not in str(e).lower():
                _ray_init_failed = True
                logger.warning("[Ray] Init failed (ValueError): %s. Ray features disabled.", e)
        except Exception as e:
            _ray_init_failed = True
            logger.warning("[Ray] Cannot connect to cluster: %s. Ray features disabled.", e)

# Re-export ray for convenience
ray = _ray

__all__ = ["ray"]
