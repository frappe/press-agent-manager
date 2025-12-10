# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


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
		status: DF.Literal["Pending", "Running", "Success", "Failure", "Skipped"]
		step_name: DF.Data
		traceback: DF.Text | None
	# end: auto-generated types

	pass


def on_doctype_update():
	frappe.db.add_index("Agent Job Step", ["creation"])
