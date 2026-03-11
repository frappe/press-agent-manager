// Copyright (c) 2025, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on("Agent Settings", {
	refresh(frm) {
		if (!frm.doc.admin_user) {
			frm.add_custom_button(__("Setup User"), () => {
				frm.call("setup_user").then(() => {
					frm.reload_doc();
				});
			});
		}

		frm.add_custom_button(__("Ping Control Plane"), () => {
			frm.call("ping_controlplane");
		});
	}
});
