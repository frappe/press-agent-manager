import frappe
from pydantic import BaseModel, model_validator

from press_base.control_plane.api.control_plane import control_plane_router
from press_base.press_base import api_docs, jsonify

remote_jobs_router = control_plane_router.subrouter(
	"remote-jobs",
	name="Remote Jobs",
	description="Following APIs will be used fetch and manage remote jobs. This communication will be between Control Plane and Agents.",
)


@remote_jobs_router.get()
@api_docs(
	responses={
		200: {
			"description": "List of queued jobs",
			"example": [
				{
					"name": "019b0a1b-5e1e-7fc2-bf91-4f873684b4a0",
					"job_type": "Pull Image",
					"request_data": {"image": "ubuntu:latest"},
				}
			],
		}
	}
)
def list_queued_jobs():
	"""
	Return a list of queued jobs
	"""

	jobs = frappe.get_list(
		"Remote Job",
		{"status": "Queued"},
		["name", "job_type", "request_data"],
	)
	# Parse request data
	for job in jobs:
		job["request_data"] = frappe.parse_json(job["request_data"])
	return jsonify(jobs)


class JobAckowledgement(BaseModel):
	name: str
	enqueued: bool = False
	rejected: bool = False
	rejection_reason: str | None = None


@remote_jobs_router.put()
def acknowledge_jobs(payload: list[JobAckowledgement]):
	"""
	Acknowledge multiple jobs
	"""

	for job in payload:
		if not frappe.db.exists("Remote Job", job.name):
			continue

		new_status = None
		if job.rejected:
			new_status = "Rejected"
		elif job.enqueued:
			new_status = "Pending"

		if new_status:
			frappe.db.set_value("Remote Job", job.name, "status", new_status)

		if job.rejected:
			frappe.db.set_value("Remote Job", job.name, "rejection_reason", job.rejection_reason or "Unknown")

	return None
