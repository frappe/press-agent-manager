from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

import frappe
from frappe.utils import get_datetime
from pydantic import BaseModel, field_validator

from press_agent_manager.control_plane.api.control_plane import control_plane_router
from press_agent_manager.press_agent_manager import api_docs, jsonify

if TYPE_CHECKING:
	from press_agent_manager.control_plane.doctype.remote_job.remote_job import RemoteJob

remote_jobs_router = control_plane_router.subrouter(
	"remote-jobs",
	name="Remote Jobs",
	description="Following APIs will be used to fetch and manage remote jobs. Agent will use these APIs to communicate with Control Plane.",
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

	@field_validator("rejection_reason")
	def truncate_reason(cls, v):
		if v is None:
			return v
		return v[:1000]


@remote_jobs_router.post("acknowledge")
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


class RemoteJobStatus(str, Enum):
	QUEUED = "Queued"
	PENDING = "Pending"
	RUNNING = "Running"
	SUCCESS = "Success"
	FAILURE = "Failure"


class RemoteJobStepStatus(str, Enum):
	PENDING = "Pending"
	RUNNING = "Running"
	SUCCESS = "Success"
	FAILURE = "Failure"


class RemoteJobSyncDetails(BaseModel):
	status: RemoteJobStatus
	start: datetime | str | None = None
	end: datetime | str | None = None
	data: str | None = None
	output: str | None = None
	error: str | None = None
	traceback: str | None = None
	version_counter: int


class RemoteJobStepSyncDetails(BaseModel):
	name: str
	step_name: str
	status: RemoteJobStepStatus
	start: datetime | str | None = None
	end: datetime | str | None = None
	data: str | None = None
	output: str | None = None
	error: str | None = None
	traceback: str | None = None
	version_counter: int


@remote_jobs_router.post("<string:job_id>/sync-job")
def sync_job(job_id: str, payload: RemoteJobSyncDetails):
	"""
	Sync job details partially
	"""

	job: RemoteJob = frappe.get_doc("Remote Job", job_id, for_update=True)  # type: ignore
	job.sync_info(
		payload.status.value,
		get_datetime(payload.start),
		get_datetime(payload.end),
		payload.data,
		payload.output,
		payload.error,
		payload.traceback,
		payload.version_counter,
	)


@remote_jobs_router.post("<string:job_id>/sync-step")
def sync_job_step(job_id: str, payload: RemoteJobStepSyncDetails):
	"""
	Sync job step details
	"""

	job: RemoteJob = frappe.get_doc("Remote Job", job_id, for_update=True)  # type: ignore
	job.sync_job_step(
		payload.name,
		payload.step_name,
		payload.status.value,
		get_datetime(payload.start),
		get_datetime(payload.end),
		payload.output,
		payload.data,
		payload.error,
		payload.traceback,
		payload.version_counter,
	)


class RemoteJobCompletionDetails(RemoteJobSyncDetails):
	steps: list[RemoteJobStepSyncDetails]


@remote_jobs_router.post("<string:job_id>/finalize")
def finalize_job(job_id: str, payload: RemoteJobCompletionDetails):
	"""
	Final sync for remote job.

	This will be called when the job reaches the terminal state.
	"""

	job: RemoteJob = frappe.get_doc("Remote Job", job_id, for_update=True)  # type: ignore
	job.sync_info(
		payload.status.value,
		get_datetime(payload.start),
		get_datetime(payload.end),
		payload.data,
		payload.output,
		payload.error,
		payload.traceback,
		payload.version_counter,
	)

	for step in payload.steps:
		job.sync_job_step(
			step.name,
			step.step_name,
			step.status.value,
			get_datetime(step.start),
			get_datetime(step.end),
			step.data,
			step.output,
			step.error,
			step.traceback,
			step.version_counter,
		)
