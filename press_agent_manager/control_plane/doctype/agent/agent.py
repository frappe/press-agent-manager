# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import TYPE_CHECKING

import frappe
import requests
from frappe.model.document import Document

if TYPE_CHECKING:
	from frappe.core.doctype.user.user import User


class Agent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		admin_user_api_key: DF.Data | None
		admin_user_api_secret: DF.Password | None
		enabled: DF.Check
		host: DF.Data
		port: DF.Int
		scheme: DF.Literal["http", "https"]
		user: DF.Link | None
	# end: auto-generated types

	@property
	def agent_base_url(self):
		return f"{self.scheme}://{self.host}:{self.port}"

	@frappe.whitelist()
	def ping(self):
		try:
			response = self.send_request("GET", "/api/method/frappe.auth.get_logged_user")
			if response.status_code == 200:
				frappe.msgprint("Agent is reachable")
			elif response.status_code in [401, 403]:
				frappe.msgprint("Agent is reachable but <b>unauthorized</b>")
			else:
				frappe.msgprint("Agent is offline. Status code: " + str(response.status_code))
		except requests.exceptions.RequestException as e:
			frappe.msgprint(f"Error pinging agent: {e}")

	# Hooks
	def after_insert(self):
		user: User = frappe.new_doc("User")  # type: ignore
		assert self.name is not None, "Agent name is required"
		user.first_name = self.name
		user.email = f"{self.name}@press.local"
		user.owner = user.email
		user.append_roles("Agent Resource Owner")
		user.time_zone = "UTC"
		user.flags.no_welcome_mail = True
		user.save()
		self.user = user.name
		self.save()

	def on_update(self):
		if self.has_value_changed("enabled") and self.user:
			frappe.db.set_value("User", self.user, "enabled", self.enabled)

	def on_trash(self):
		if self.user:
			frappe.db.set_value("User", self.user, "enabled", 0)

	# Helper
	def send_request(self, method, endpoint, data=None):
		if not endpoint.startswith("/"):
			endpoint = "/" + endpoint

		url = self.agent_base_url + endpoint
		response = requests.request(
			method,
			url,
			headers={
				"Authorization": f"token {self.admin_user_api_key}:{self.get_password('admin_user_api_secret')}"
			},
			json=data,
		)
		return response
