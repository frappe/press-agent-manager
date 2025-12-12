__version__ = "0.0.1"

# Register routers
from press_base.control_plane.api.control_plane import control_plane_router
from press_base.control_plane.api.remote_jobs import remote_jobs_router

__all__ = [
	"control_plane_router",
	"remote_jobs_router",
]
