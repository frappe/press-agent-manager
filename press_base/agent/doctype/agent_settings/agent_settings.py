# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from typing import TYPE_CHECKING

import frappe
import requests
from frappe.model.document import Document

if TYPE_CHECKING:
	from frappe.core.doctype.user.user import User


class AgentSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		admin_user: DF.Link
		controlplane_api_key: DF.Data
		controlplane_api_secret: DF.Password
		controlplane_host: DF.Data
		controlplane_port: DF.Int
		controlplane_scheme: DF.Literal["http", "https"]
		registered_agent_id: DF.Data
	# end: auto-generated types

	@property
	def controlplane_base_url(self):
		return f"{self.controlplane_scheme}://{self.controlplane_host}:{self.controlplane_port}"

	@frappe.whitelist()
	def ping_controlplane(self):
		try:
			response = self.send_request_to_controlplane("GET", "/api/method/frappe.auth.get_logged_user")
			if response.status_code == 200:
				frappe.msgprint("Control Plane is reachable")
			elif response.status_code in [401, 403]:
				frappe.msgprint("Control Plane is reachable but <b>unauthorized</b>")
			else:
				frappe.msgprint("Control Plane is offline. Status code: " + str(response.status_code))
		except requests.exceptions.RequestException as e:
			frappe.msgprint(f"Error pinging Control Plane: {e}")

	@frappe.whitelist()
	def setup_user(self):
		frappe.only_for("System Manager")
		if self.admin_user:
			return

		user: User = frappe.new_doc("User")  # type: ignore
		assert self.name is not None, "Agent name is required"
		user.first_name = self.name
		user.email = "agent-admin@press.local"
		user.owner = user.email
		user.append_roles("Agent Admin")
		user.time_zone = "UTC"
		user.flags.no_welcome_mail = True
		user.save()
		assert user.name is not None, "User name is blank"
		self.admin_user = user.name
		self.save()

	# Helper Methods
	def send_request_to_controlplane(self, method, endpoint, data=None):
		if not endpoint.startswith("/"):
			endpoint = "/" + endpoint

		url = self.controlplane_base_url + endpoint
		response = requests.request(
			method,
			url,
			headers={
				"Authorization": f"token {self.controlplane_api_key}:{self.get_password('controlplane_api_secret')}"
			},
			json=data,
		)
		return response
