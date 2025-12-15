__version__ = "0.0.1"

# Register routers
from press_base.control_plane.api.control_plane import control_plane_router
from press_base.control_plane.api.remote_jobs import remote_jobs_router

# Default imports
from press_base.press_base.ansible import Ansible, AnsibleAdHoc
from press_base.press_base.rest_api import Router, api_docs, jsonify

__all__ = [
	"Ansible",
	"AnsibleAdHoc",
	"Router",
	"api_docs",
	"control_plane_router",
	"jsonify",
	"remote_jobs_router",
]
