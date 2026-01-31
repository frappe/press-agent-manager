// Copyright (c) 2026, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on("Virtual Machine", {
	refresh(frm) {
		[["Ping", "ping"]].forEach(([label, method]) => {
			frm.add_custom_button(
				label,
				() => {
					// Ask confirmation
					frappe.confirm(
						`Are you sure you want to ${label.toLowerCase()} this virtual machine?`,
						() => {
							frm.call(method).then(() => frm.refresh());
						},
					);
				},
				"Actions",
			);
		});
	},
});
