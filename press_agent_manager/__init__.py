__version__ = "0.0.1"

from press_agent_manager.control_plane.api.control_plane import control_plane_router
from press_agent_manager.control_plane.api.remote_jobs import remote_jobs_router
from press_agent_manager.infrastructure.ansible import Ansible, AnsibleAdHoc
from press_agent_manager.press_agent_manager.rest_api import Router, api_docs, jsonify

__all__ = [
	"Ansible",
	"AnsibleAdHoc",
	"Router",
	"api_docs",
	"control_plane_router",
	"jsonify",
	"remote_jobs_router",
]
