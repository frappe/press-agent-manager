# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import TYPE_CHECKING

import frappe
from frappe.model.document import Document

if TYPE_CHECKING:
	from press_agent_manager.infrastructure.ansible import AnsibleStepResult
	from press_agent_manager.infrastructure.doctype.ansible_play.ansible_play import AnsiblePlay


class VirtualMachine(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		memory_mb: DF.Int
		private_ip_address: DF.Data
		provider: DF.Literal["Generic"]
		public_ip_address: DF.Data
		ssh_port: DF.Int
		status: DF.Literal["Pending", "Active", "Stopped", "Terminated"]
		vcpus: DF.Int
	# end: auto-generated types

	@property
	def ssh_host(self):
		return self.public_ip_address

	@frappe.whitelist()
	def ping(self):
		play = self.run_ansible_play("press_agent_manager", "playbooks/ping.yml", run_in_background=True)
		frappe.msgprint(f"Created Ansible Play <a href='{play.get_url()}'>View Play</a>")

	# Utility Functions

	def run_command(self, command: str) -> AnsibleStepResult:
		from press_agent_manager.infrastructure.ansible import AnsibleAdHoc

		adhoc = AnsibleAdHoc(sources=[self.ssh_host], port=self.ssh_port)
		results = adhoc.run(command)
		if self.ssh_host not in results:
			frappe.throw(f"Command failed on {self.ssh_host}. No results.")

		return results[self.ssh_host]

	def run_playbook(self, playbook_yaml: str) -> list[AnsibleStepResult]:
		from press_agent_manager.infrastructure.ansible import AnsibleAdHoc

		adhoc = AnsibleAdHoc(sources=[self.ssh_host], port=self.ssh_port)
		results = adhoc.run_playbook(playbook_yaml)
		return results.get(self.ssh_host, [])

	def run_ansible_play(
		self,
		app: str,
		playbook_path: str,
		variables: dict | None = None,
		debug: bool = False,
		reference_doctype: str | None = None,
		reference_name: str | None = None,
		run_in_background: bool = False,
	) -> AnsiblePlay:
		from press_agent_manager.infrastructure.ansible import Ansible

		if (reference_doctype is None) != (reference_name is None):
			frappe.throw("Either both or neither reference_doctype and reference_name must be provided")

		playbook = Ansible(
			app=app,
			playbook_path=playbook_path,
			variables=variables or {},
			host=self.ssh_host,
			port=self.ssh_port,
			debug=debug,
			reference_doctype=reference_doctype or self.doctype,
			reference_name=reference_name or self.name,
		)

		return playbook.run(run_in_background)
