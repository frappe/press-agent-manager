// Copyright (c) 2025, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on("Agent", {
	refresh(frm) {
		frm.add_custom_button("Ping", () => {
			frm.call("ping");
		});
	}
});
