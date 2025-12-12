# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

from datetime import time

from frappe.model.document import Document
from frappe.utils.data import cint, get_datetime

from press_base.agent.realtime import send_realtime_event_to_controlplane


class AgentJobStep(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		agent_job: DF.Link
		data: DF.Text | None
		end: DF.Datetime | None
		error: DF.SmallText | None
		output: DF.Text | None
		start: DF.Datetime | None
		status: DF.Literal["Pending", "Running", "Success", "Failure"]
		step_name: DF.Data
		traceback: DF.Text | None
		version_counter: DF.Int
	# end: auto-generated types

	def on_update(self):
		self.notify_controlplane()
		self.increment_version_counter()

	def increment_version_counter(self):
		self.version_counter += 1
		self.db_update()

	def notify_controlplane(self):
		if self.is_new():
			return

		send_realtime_event_to_controlplane(
			"remote_job.sync_step",
			{
				"job_id": self.agent_job,
				"data": {
					"name": self.name,
					"step_name": self.step_name,
					"status": self.status,
					"start": self.start,
					"end": self.end,
					"output": self.output,
					"data": self.data,
					"error": self.error,
					"traceback": self.traceback,
					"version_counter": self.version_counter,
				},
			},
		)
