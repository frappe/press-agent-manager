# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from press_base.agent.realtime import send_realtime_event_to_controlplane


class AgentJobStep(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		agent_job: DF.Link
		data: DF.Text | None
		duration: DF.Time | None
		end: DF.Datetime | None
		error: DF.SmallText | None
		output: DF.Text | None
		start: DF.Datetime | None
		status: DF.Literal["Pending", "Running", "Success", "Failure"]
		step_name: DF.Data
		traceback: DF.Text | None
	# end: auto-generated types

	def on_update(self):
		self.notify_controlplane()

	def notify_controlplane(self):
		if self.is_new():
			return

		send_realtime_event_to_controlplane(
			"remote_job.sync_step",
			{
				"job_id": self.agent_job,
				"data": {
					"step_name": self.step_name,
					"status": self.status,
					"start": self.start,
					"end": self.end,
					"output": self.output,
					"data": self.data,
					"error": self.error,
					"traceback": self.traceback,
				},
			},
		)
