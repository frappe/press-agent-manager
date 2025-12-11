# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RemoteJobType(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from press_base.control_plane.doctype.remote_job_type_step.remote_job_type_step import (
			RemoteJobTypeStep,
		)

		steps: DF.Table[RemoteJobTypeStep]
	# end: auto-generated types

	pass
