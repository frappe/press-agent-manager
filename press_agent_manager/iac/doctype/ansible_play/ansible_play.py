# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AnsiblePlay(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		changed: DF.Int
		duration: DF.Duration | None
		end: DF.Datetime | None
		failures: DF.Int
		host: DF.Data
		ignored: DF.Int
		ok: DF.Int
		play: DF.Data | None
		playbook: DF.Data | None
		port: DF.Int
		processed: DF.Int
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		rescued: DF.Int
		skipped: DF.Int
		start: DF.Datetime | None
		status: DF.Literal["Pending", "Running", "Success", "Failure"]
		unreachable: DF.Int
		user: DF.Data
		variables: DF.Code | None
	# end: auto-generated types

	def on_trash(self):
		tasks = frappe.get_all("Ansible Task", filters={"play": self.name}, pluck="name")
		for task in tasks:
			frappe.delete_doc("Ansible Task", task)
