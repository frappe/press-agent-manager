from __future__ import annotations

from contextlib import suppress
from functools import cached_property
from typing import TYPE_CHECKING

import frappe
import redis

from press_agent_manager.control_plane.api.remote_jobs import JobAckowledgement, RemoteJobCompletionDetails
from press_agent_manager.press_agent_manager.utils import pydantic_serialize

if TYPE_CHECKING:
	from press_agent_manager.agent.doctype.agent_settings.agent_settings import AgentSettings


class ControlPlane:
	def __init__(self):
		self.settings: AgentSettings = frappe.get_single("Agent Settings")  # type: ignore

	def poll_queued_jobs(self):
		if not self.settings.enabled:
			return

		response = self.settings.send_request_to_controlplane("GET", "/api/control-plane/remote-jobs")
		response.raise_for_status()

		jobs = response.json()
		acknowledgements: list[JobAckowledgement] = []

		for job in jobs:
			job_type = job["job_type"]
			job_name = job["name"]
			if job_type not in self.agent_job_handlers:
				acknowledgements.append(
					JobAckowledgement(
						name=job_name,
						rejected=True,
						rejection_reason=f"No handler found for job type : {job_type}",
					)
				)
				continue

			try:
				queued = frappe.get_attr(self.agent_job_handlers[job_type])(
					job_name, job_type, job["request_data"]
				)
				if not queued:
					continue
				acknowledgements.append(JobAckowledgement(name=job_name, enqueued=True))
			except Exception as e:
				acknowledgements.append(
					JobAckowledgement(
						name=job_name,
						rejected=True,
						rejection_reason=f"Failed to call {self.agent_job_handlers[job_type]}: {e}",
					)
				)

		self.acknowledge_jobs(acknowledgements)

	def acknowledge_jobs(self, jobs: list[JobAckowledgement]):
		"""
		Acknowledge multiple jobs
		"""
		self.settings.send_request_to_controlplane(
			"POST", "/api/control-plane/remote-jobs/acknowledge", data=pydantic_serialize(jobs)
		)

	def submit_job(self, job_id: str, data: RemoteJobCompletionDetails):
		"""
		Submit the job to controlplane
		"""
		self.settings.send_request_to_controlplane(
			"POST", f"/api/control-plane/remote-jobs/{job_id}/finalize", data=pydantic_serialize(data)
		)

	@cached_property
	def agent_job_handlers(self) -> dict[str, str]:
		return {
			job_type: handlers[0]
			for job_type, handlers in frappe.get_hooks("agent_job_handlers", default={}).items()
			if handlers
		}


def poll_queued_jobs(*args, **kwargs):
	frappe.enqueue(ControlPlane().poll_queued_jobs, job_id="poll_queued_jobs", timeout=600, deduplicate=True)
