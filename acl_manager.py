import json
import os
import subprocess
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import urllib.request
import urllib.error
import customtkinter as ctk
import json5

from topology_editor import TopologyEditor


# Set custom styling and base themes
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class CustomDialog(ctk.CTkToplevel):
    """
    Industry-standard modal dialog for rule creation and selection.
    """
    def __init__(
        self, parent, title, labels, options, show_ports=True, default_values=None
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry("450x380")
        self.resizable(False, False)
        self.configure(fg_color="#1e293b")

        # Make transient relative to parent and grab focus (modal behavior)
        self.transient(parent)
        self.grab_set()

        self.result = None

        # Dialog Title
        ctk.CTkLabel(
            self,
            text=title.upper(),
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#60a5fa"
        ).pack(pady=(20, 10))

        self.boxes = []
        for i, (lbl, opts) in enumerate(zip(labels, options)):
            ctk.CTkLabel(
                self,
                text=lbl,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color="#f8fafc"
            ).pack(pady=(10, 2))

            box = ctk.CTkComboBox(
                self,
                values=opts,
                width=350,
                fg_color="#0f172a",
                border_color="#334155",
                button_color="#3b82f6",
                button_hover_color="#2563eb",
                dropdown_fg_color="#1e293b",
                dropdown_hover_color="#334155"
            )
            if default_values and len(default_values) > i:
                box.set(default_values[i])
            else:
                if opts:
                    box.set(opts[0])
            box.pack(pady=5)
            self.boxes.append(box)

        self.show_ports = show_ports
        if show_ports:
            ctk.CTkLabel(
                self,
                text="Ports (e.g., '*', '22', '80,443'):",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color="#f8fafc"
            ).pack(pady=(10, 2))
            self.port_entry = ctk.CTkEntry(
                self,
                width=350,
                fg_color="#0f172a",
                border_color="#334155",
                text_color="#f8fafc"
            )
            if default_values and len(default_values) > len(labels):
                self.port_entry.insert(0, default_values[-1])
            else:
                self.port_entry.insert(0, "*")
            self.port_entry.pack(pady=5)

        # Buttons
        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(pady=(25, 10))

        btn_submit = ctk.CTkButton(
            btn_f,
            text="Confirm",
            fg_color="#10b981",
            hover_color="#059669",
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            command=self.submit
        )
        btn_submit.pack(side="left", padx=10)

        btn_cancel = ctk.CTkButton(
            btn_f,
            text="Cancel",
            fg_color="#475569",
            hover_color="#334155",
            text_color="white",
            command=self.cancel
        )
        btn_cancel.pack(side="left", padx=10)

        # Center on the parent window
        self.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        w = self.winfo_width()
        h = self.winfo_height()
        x = parent_x + (parent_w - w) // 2
        y = parent_y + (parent_h - h) // 2
        self.geometry(f"+{x}+{y}")

        # Wait for dialog window to be closed
        self.wait_window()

    def submit(self):
        res = [b.get() for b in self.boxes]
        if self.show_ports:
            res.append(self.port_entry.get())
        self.result = res
        self.destroy()

    def cancel(self):
        self.destroy()


class DeviceTagOwnersDialog(ctk.CTkToplevel):
    """
    Dialog to manage tag owners (tagOwners in ACL) for the tags of a device.
    """
    def __init__(self, parent, hostname, device_tags, acl_data, all_groups):
        super().__init__(parent)
        self.title(f"Manage Tag Owners: {hostname}")
        self.geometry("520x450")
        self.resizable(False, False)
        self.configure(fg_color="#1e293b")

        self.transient(parent)
        self.grab_set()

        self.hostname = hostname
        self.device_tags = device_tags
        self.acl_data = acl_data
        self.all_groups = all_groups
        self.saved = False

        # Work on a copy of the tagOwners mapping to allow Cancel without side effects
        self.temp_tag_owners = {}
        tag_owners_section = acl_data.setdefault("tagOwners", {})
        for t in self.device_tags:
            self.temp_tag_owners[t] = list(tag_owners_section.get(t, []))

        # Title
        ctk.CTkLabel(
            self,
            text=f"MANAGE TAG OWNERS FOR {hostname.upper()}",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#60a5fa"
        ).pack(pady=(15, 10))

        if not self.device_tags:
            ctk.CTkLabel(
                self,
                text="This device has no assigned tags.\n\nOnly tagged devices have tag owners. Assign tags to the physical device\nfirst, or manage tag owners directly from the Tags tab.",
                font=ctk.CTkFont(family="Segoe UI", size=12, slant="italic"),
                text_color="#ef4444",
                justify="center"
            ).pack(pady=40, padx=25)
            
            ctk.CTkButton(
                self,
                text="Close",
                width=100,
                fg_color="#475569",
                hover_color="#334155",
                text_color="white",
                command=self.destroy
            ).pack(pady=10)
            
            # Center dialog
            self.center_dialog(parent)
            self.wait_window()
            return

        # Tag Selector (if there are multiple tags)
        self.selected_tag = self.device_tags[0]
        if len(self.device_tags) > 1:
            sel_frame = ctk.CTkFrame(self, fg_color="transparent")
            sel_frame.pack(fill="x", padx=25, pady=5)
            ctk.CTkLabel(
                sel_frame,
                text="Select Tag to Edit:",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color="#f8fafc"
            ).pack(side="left", padx=(0, 10))
            
            self.tag_menu = ctk.CTkOptionMenu(
                sel_frame,
                values=self.device_tags,
                command=self.on_tag_changed,
                fg_color="#0f172a",
                button_color="#334155",
                button_hover_color="#475569",
                dropdown_fg_color="#1e293b",
                dropdown_hover_color="#334155"
            )
            self.tag_menu.pack(side="left", fill="x", expand=True)
            self.tag_menu.set(self.selected_tag)
        else:
            ctk.CTkLabel(
                self,
                text=f"Editing Owners for: {self.selected_tag}",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color="#38bdf8"
            ).pack(pady=(5, 5))

        # Current Owners List
        ctk.CTkLabel(
            self,
            text="Current Owners (Users/Groups):",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#f8fafc"
        ).pack(anchor="w", padx=25, pady=(5, 2))

        self.owners_scroll = ctk.CTkScrollableFrame(
            self,
            width=450,
            height=140,
            fg_color="#0f172a",
            border_width=1,
            border_color="#334155"
        )
        self.owners_scroll.pack(padx=25, pady=5)

        # Add Owner Frame
        ctk.CTkLabel(
            self,
            text="Add Owner Group:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#f8fafc"
        ).pack(anchor="w", padx=25, pady=(10, 2))

        add_f = ctk.CTkFrame(self, fg_color="transparent")
        add_f.pack(fill="x", padx=25, pady=2)

        self.group_combo = ctk.CTkComboBox(
            add_f,
            values=[""] + self.all_groups,
            width=320,
            fg_color="#0f172a",
            border_color="#334155",
            dropdown_fg_color="#1e293b",
            dropdown_hover_color="#334155"
        )
        self.group_combo.pack(side="left", padx=(0, 10))
        if self.all_groups:
            self.group_combo.set(self.all_groups[0])

        btn_add = ctk.CTkButton(
            add_f,
            text="➕ Add",
            width=80,
            fg_color="#3b82f6",
            hover_color="#2563eb",
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            command=self.add_group_owner
        )
        btn_add.pack(side="right")

        # Or Custom Owner Box (email)
        ctk.CTkLabel(
            self,
            text="Or add custom owner (e.g. user@domain.com, group:shiner-tech, autogroup:admin):",
            font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
            text_color="#94a3b8"
        ).pack(anchor="w", padx=25, pady=(5, 0))

        custom_f = ctk.CTkFrame(self, fg_color="transparent")
        custom_f.pack(fill="x", padx=25, pady=2)

        self.custom_entry = ctk.CTkEntry(
            custom_f,
            placeholder_text="user@example.com or group:name",
            width=320,
            fg_color="#0f172a",
            border_color="#334155",
            text_color="#f8fafc"
        )
        self.custom_entry.pack(side="left", padx=(0, 10))

        btn_add_custom = ctk.CTkButton(
            custom_f,
            text="➕ Add",
            width=80,
            fg_color="#10b981",
            hover_color="#059669",
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            command=self.add_custom_owner
        )
        btn_add_custom.pack(side="right")

        # Bottom Action Buttons
        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(pady=(20, 10), fill="x", padx=25)

        btn_save = ctk.CTkButton(
            btn_f,
            text="Save Changes",
            fg_color="#10b981",
            hover_color="#059669",
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            command=self.save
        )
        btn_save.pack(side="right", padx=5)

        btn_cancel = ctk.CTkButton(
            btn_f,
            text="Cancel",
            fg_color="#475569",
            hover_color="#334155",
            text_color="white",
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=5)

        self.refresh_owners_list()
        self.center_dialog(parent)
        self.wait_window()

    def center_dialog(self, parent):
        self.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        w = self.winfo_width()
        h = self.winfo_height()
        x = parent_x + (parent_w - w) // 2
        y = parent_y + (parent_h - h) // 2
        self.geometry(f"+{x}+{y}")

    def on_tag_changed(self, tag):
        self.selected_tag = tag
        self.refresh_owners_list()

    def refresh_owners_list(self):
        for w in self.owners_scroll.winfo_children():
            w.destroy()

        owners = self.temp_tag_owners.get(self.selected_tag, [])
        if not owners:
            ctk.CTkLabel(
                self.owners_scroll,
                text="No owners assigned to this tag (orphaned tag).",
                font=ctk.CTkFont(slant="italic"),
                text_color="#ef4444"
            ).pack(pady=10)
            return

        for o in owners:
            row = ctk.CTkFrame(self.owners_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            disp_owner = o.replace("group:", "👥 ").replace("autogroup:", "⚙️ ").replace("user:", "👤 ")
            ctk.CTkLabel(
                row,
                text=disp_owner,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color="#e2e8f0"
            ).pack(side="left", padx=5)

            btn_del = ctk.CTkButton(
                row,
                text="×",
                width=20,
                height=20,
                fg_color="transparent",
                text_color="#ef4444",
                hover_color="#7f1d1d",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda owner_val=o: self.remove_owner(owner_val)
            )
            btn_del.pack(side="right", padx=5)

    def add_group_owner(self):
        val = self.group_combo.get().strip()
        if val:
            owners = self.temp_tag_owners.setdefault(self.selected_tag, [])
            if val not in owners:
                owners.append(val)
                self.refresh_owners_list()

    def add_custom_owner(self):
        val = self.custom_entry.get().strip()
        if val:
            owners = self.temp_tag_owners.setdefault(self.selected_tag, [])
            if val not in owners:
                owners.append(val)
                self.custom_entry.delete(0, "end")
                self.refresh_owners_list()

    def remove_owner(self, owner):
        owners = self.temp_tag_owners.get(self.selected_tag, [])
        if owner in owners:
            owners.remove(owner)
            self.refresh_owners_list()

    def save(self):
        # Commit temporary mapping back to original acl_data
        tag_owners_section = self.acl_data.setdefault("tagOwners", {})
        for t, owners in self.temp_tag_owners.items():
            tag_owners_section[t] = owners
        self.saved = True
        self.destroy()


class ACLManagerV5(ctk.CTk):
    """
    Main Application Window containing the refurbished dashboard.
    """
    def __init__(self):
        super().__init__()
        self.title("Tailscale Access Control Console")
        self.geometry("1280x820")
        self.minsize(1100, 700)

        self.acl_data = {"groups": {}, "tagOwners": {}, "acls": [], "ssh": []}
        self.current_tag = None
        self.current_filepath = None
        self.cli_devices = []

        # Configure layout (2 columns: Sidebar and Main Content Area)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)  # Sidebar (no scaling)
        self.grid_columnconfigure(1, weight=1)  # Content area (scaling)

        self.setup_sidebar()
        self.setup_main_content()

        # Load initial configuration profiles
        self.autoload_last_config()

    # ---- LAYOUT BUILDERS ----
    def setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=("#1e293b", "#0f172a"))
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.pack_propagate(False)

        # Brand Logo and Subtext
        self.brand_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.brand_frame.pack(fill="x", padx=20, pady=(25, 20))

        self.lbl_logo = ctk.CTkLabel(
            self.brand_frame,
            text="🛡️ TAILSCALE ACL",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=("#3b82f6", "#38bdf8")
        )
        self.lbl_logo.pack(anchor="w")

        self.lbl_subtitle = ctk.CTkLabel(
            self.brand_frame,
            text="Console & Editor v6.0",
            font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
            text_color=("#64748b", "#94a3b8")
        )
        self.lbl_subtitle.pack(anchor="w", pady=(2, 0))

        # Nav Buttons list container
        self.nav_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.nav_frame.pack(fill="both", expand=True, padx=15)

        self.nav_buttons = {}
        nav_items = [
            ("overview", "📊  Overview"),
            ("rules", "🛡️  Access Rules"),
            ("tags", "🏷️  Network Tags"),
            ("groups", "👥  Groups Manager"),
            ("devices", "💻  Live Devices"),
            ("topology", "🗺️  Topology Editor"),
            ("raw", "📝  Raw JSON"),
            ("chatbot", "🤖  AI Assistant"),
        ]

        for page_key, label in nav_items:
            btn = ctk.CTkButton(
                self.nav_frame,
                text=label,
                anchor="w",
                height=38,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                fg_color="transparent",
                text_color=("#475569", "#cbd5e1"),
                hover_color=("#cbd5e1", "#1e293b"),
                command=lambda k=page_key: self.show_page(k)
            )
            btn.pack(fill="x", pady=3)
            self.nav_buttons[page_key] = btn

        # Bottom Configuration Actions Panel
        self.bottom_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.bottom_frame.pack(fill="x", side="bottom", padx=15, pady=20)

        # Subtle divider line
        ctk.CTkFrame(self.bottom_frame, height=2, fg_color=("#e2e8f0", "#1e293b")).pack(fill="x", pady=(0, 15))

        self.btn_load = ctk.CTkButton(
            self.bottom_frame,
            text="📥 Load Config",
            fg_color=("#3b82f6", "#2563eb"),
            hover_color=("#2563eb", "#1d4ed8"),
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            command=self.load_json
        )
        self.btn_load.pack(fill="x", pady=4)

        self.btn_save = ctk.CTkButton(
            self.bottom_frame,
            text="💾 Save Config",
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            command=self.save_json
        )
        self.btn_save.pack(fill="x", pady=4)

        self.lbl_status = ctk.CTkLabel(
            self.bottom_frame,
            text="Status: Ready.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#64748b", "#94a3b8"),
            justify="left",
            anchor="w",
            wraplength=200
        )
        self.lbl_status.pack(fill="x", pady=(10, 0))

    def setup_main_content(self):
        self.content_frame = ctk.CTkFrame(self, fg_color=("#f8fafc", "#0b0f19"), corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        self.pages = {}

        # Initialize distinct page panels
        self.page_overview = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.page_rules = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.page_tags = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.page_groups = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.page_devices = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.page_topology = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.page_raw = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.page_chatbot = ctk.CTkFrame(self.content_frame, fg_color="transparent")

        self.pages["overview"] = self.page_overview
        self.pages["rules"] = self.page_rules
        self.pages["tags"] = self.page_tags
        self.pages["groups"] = self.page_groups
        self.pages["devices"] = self.page_devices
        self.pages["topology"] = self.page_topology
        self.pages["raw"] = self.page_raw
        self.pages["chatbot"] = self.page_chatbot

        # Build each separate page interface
        self.setup_overview_page()
        self.setup_rules_tab()
        self.setup_tags_tab()
        self.setup_groups_tab()
        self.setup_devices_tab()
        self.setup_raw_tab()
        self.setup_topology_tab()
        self.setup_chatbot_page()

        # Display defaults
        self.show_page("overview")

    def show_page(self, page_name):
        # Hide current pages
        for page in self.pages.values():
            page.grid_forget()

        # Render selected page
        self.pages[page_name].grid(row=0, column=0, sticky="nsew", padx=24, pady=24)

        # Highlight sidebar active button and reset inactive
        for name, btn in self.nav_buttons.items():
            if name == page_name:
                btn.configure(
                    fg_color=("#3b82f6", "#2563eb"),
                    text_color="white",
                    hover_color=("#2563eb", "#1d4ed8")
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=("#475569", "#cbd5e1"),
                    hover_color=("#e2e8f0", "#1e293b")
                )

    # ---- PAGE SETUP IMPLEMENTATIONS ----
    def setup_overview_page(self):
        self.page_overview.grid_columnconfigure(0, weight=1)
        self.page_overview.grid_rowconfigure(2, weight=1)

        # Header Title
        title_f = ctk.CTkFrame(self.page_overview, fg_color="transparent")
        title_f.grid(row=0, column=0, sticky="ew", pady=(10, 20))

        ctk.CTkLabel(
            title_f,
            text="Access Control Overview",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
        ).pack(anchor="w")

        self.lbl_overview_subtitle = ctk.CTkLabel(
            title_f,
            text="No config file loaded.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=("#64748b", "#94a3b8")
        )
        self.lbl_overview_subtitle.pack(anchor="w", pady=(2, 0))

        # KPI Dashboard Cards
        self.stats_frame = ctk.CTkFrame(self.page_overview, fg_color="transparent")
        self.stats_frame.grid(row=1, column=0, sticky="ew", pady=10)
        self.stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="stats")

        self.card_rules = self.create_stat_card(self.stats_frame, 0, "🛡️", "Access Rules", "0 Rules", "#10b981")
        self.card_tags = self.create_stat_card(self.stats_frame, 1, "🏷️", "Network Tags", "0 Tags", "#f97316")
        self.card_groups = self.create_stat_card(self.stats_frame, 2, "👥", "Groups Manager", "0 Groups", "#8b5cf6")
        self.card_devices = self.create_stat_card(self.stats_frame, 3, "💻", "Live Devices", "0 Devices", "#64748b")

        # Metadata Card Info Box
        self.info_box = ctk.CTkFrame(
            self.page_overview,
            fg_color=("#ffffff", "#1e293b"),
            border_width=1,
            border_color=("#e2e8f0", "#334155")
        )
        self.info_box.grid(row=2, column=0, sticky="nsew", pady=(20, 10))

        ctk.CTkLabel(
            self.info_box,
            text="Configuration File Metadata",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(20, 10))

        self.info_details_frame = ctk.CTkFrame(self.info_box, fg_color="transparent")
        self.info_details_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.meta_labels = {}
        meta_keys = [
            ("file_path", "Loaded File:"),
            ("rule_count", "Total Rules:"),
            ("tag_count", "Total Tags:"),
            ("group_count", "Total Groups:"),
            ("user_count", "Total Group Users:"),
            ("device_count", "Total Devices:"),
            ("status", "System Status:")
        ]

        for idx, (key, label_text) in enumerate(meta_keys):
            row_f = ctk.CTkFrame(self.info_details_frame, fg_color="transparent")
            row_f.pack(fill="x", pady=5)

            lbl_k = ctk.CTkLabel(
                row_f,
                text=label_text,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                width=160,
                anchor="w",
                text_color=("#475569", "#cbd5e1")
            )
            lbl_k.pack(side="left")

            lbl_v = ctk.CTkLabel(
                row_f,
                text="-",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                anchor="w",
                text_color=("#1e293b", "#f8fafc")
            )
            lbl_v.pack(side="left", fill="x", expand=True)
            self.meta_labels[key] = lbl_v

    def create_stat_card(self, parent, col, icon, title, val, color):
        card = ctk.CTkFrame(
            parent,
            fg_color=("#ffffff", "#1e293b"),
            border_width=1,
            border_color=("#e2e8f0", "#334155"),
            corner_radius=10
        )
        card.grid(row=0, column=col, padx=10, pady=5, sticky="nsew")

        # Top Section
        header_f = ctk.CTkFrame(card, fg_color="transparent")
        header_f.pack(fill="x", padx=15, pady=(15, 5))

        icon_lbl = ctk.CTkLabel(header_f, text=icon, font=ctk.CTkFont(size=22), text_color=color)
        icon_lbl.pack(side="left")

        title_lbl = ctk.CTkLabel(
            header_f,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=("#64748b", "#94a3b8")
        )
        title_lbl.pack(side="left", padx=8)

        # Big Number Value
        num_lbl = ctk.CTkLabel(card, text=val, font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"))
        num_lbl.pack(anchor="w", padx=15, pady=(5, 15))

        # Colored accent stripe at top
        accent = ctk.CTkFrame(card, height=4, fg_color=color)
        accent.place(relx=0, rely=0, relwidth=1)

        return {"num": num_lbl, "frame": card}

    def setup_rules_tab(self):
        self.page_rules.grid_rowconfigure(1, weight=1)
        self.page_rules.grid_columnconfigure(0, weight=1)

        header_f = ctk.CTkFrame(self.page_rules, fg_color="transparent")
        header_f.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        ctk.CTkLabel(
            header_f,
            text="Access Control Rules (ACLs)",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
        ).pack(side="left")

        btn_add = ctk.CTkButton(
            header_f,
            text="+ Add Access Rule",
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.create_custom_rule
        )
        btn_add.pack(side="right")

        # Scrollable table container
        self.rules_table_container = ctk.CTkFrame(
            self.page_rules,
            fg_color=("#ffffff", "#1e293b"),
            border_width=1,
            border_color=("#e2e8f0", "#334155")
        )
        self.rules_table_container.grid(row=1, column=0, sticky="nsew")
        self.rules_table_container.grid_rowconfigure(1, weight=1)
        self.rules_table_container.grid_columnconfigure(0, weight=1)

        # Header Row
        headers_f = ctk.CTkFrame(self.rules_table_container, fg_color=("#f1f5f9", "#0f172a"), height=40)
        headers_f.grid(row=0, column=0, sticky="ew")
        headers_f.pack_propagate(False)

        cols = [
            ("ID", 60),
            ("Source Node", 230),
            ("Direction", 80),
            ("Destination Node", 230),
            ("Ports", 140),
            ("Actions", 120)
        ]

        for col_name, width in cols:
            f_col = ctk.CTkFrame(headers_f, width=width, fg_color="transparent")
            f_col.pack(side="left", fill="both", padx=5)
            f_col.pack_propagate(False)

            lbl = ctk.CTkLabel(
                f_col,
                text=col_name,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=("#475569", "#94a3b8")
            )
            if col_name in ["ID", "Direction", "Actions"]:
                lbl.pack(expand=True)
            else:
                lbl.pack(side="left", fill="y", padx=5)

        # Table Row Frame Scrollable Area
        self.rules_scrollable = ctk.CTkScrollableFrame(self.rules_table_container, fg_color="transparent")
        self.rules_scrollable.grid(row=1, column=0, sticky="nsew")

    def setup_tags_tab(self):
        self.page_tags.grid_rowconfigure(0, weight=1)
        self.page_tags.grid_columnconfigure(0, weight=1)  # Left column
        self.page_tags.grid_columnconfigure(1, weight=3)  # Right column

        # Left Column - Scroll list
        left_f = ctk.CTkFrame(
            self.page_tags,
            fg_color=("#ffffff", "#1e293b"),
            border_width=1,
            border_color=("#e2e8f0", "#334155")
        )
        left_f.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        ctk.CTkLabel(
            left_f,
            text="Network Tags",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
        ).pack(pady=(15, 10))

        # Search field
        self.tag_search_var = tk.StringVar()
        self.tag_search_var.trace_add("write", lambda *args: self.refresh_tags_list())

        search_entry = ctk.CTkEntry(
            left_f,
            placeholder_text="🔍 Filter tags...",
            textvariable=self.tag_search_var,
            fg_color=("#f1f5f9", "#0f172a"),
            border_color=("#cbd5e1", "#334155")
        )
        search_entry.pack(fill="x", padx=12, pady=(0, 10))

        self.tags_scrollable = ctk.CTkScrollableFrame(left_f, fg_color="transparent")
        self.tags_scrollable.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkButton(
            left_f,
            text="+ Create New Tag",
            fg_color=("#3b82f6", "#2563eb"),
            hover_color=("#2563eb", "#1d4ed8"),
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            command=self.create_tag
        ).pack(pady=12, padx=12, fill="x")

        # Right Column - Details/Inspector
        self.setup_tags_right_panel()

    def setup_tags_right_panel(self):
        self.right_f = ctk.CTkFrame(self.page_tags, fg_color="transparent")
        self.right_f.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        # Empty state screen
        self.tag_empty_frame = ctk.CTkFrame(
            self.right_f,
            fg_color=("#ffffff", "#1e293b"),
            border_width=1,
            border_color=("#e2e8f0", "#334155")
        )
        self.tag_empty_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self.tag_empty_frame,
            text="🏷️\n\nSelect a tag from the left pane\nto view or update properties.",
            font=ctk.CTkFont(family="Segoe UI", size=14, slant="italic"),
            text_color=("#64748b", "#94a3b8"),
            justify="center"
        ).pack(expand=True)

        # Inspector Container
        self.tag_inspector_frame = ctk.CTkFrame(self.right_f, fg_color="transparent")

        # 1. Identity Box Card
        id_card = ctk.CTkFrame(
            self.tag_inspector_frame,
            fg_color=("#ffffff", "#1e293b"),
            border_width=1,
            border_color=("#e2e8f0", "#334155")
        )
        id_card.pack(fill="x", pady=(0, 12))

        header_f = ctk.CTkFrame(id_card, fg_color="transparent")
        header_f.pack(fill="x", padx=15, pady=15)

        self.lbl_tag_title = ctk.CTkLabel(
            header_f,
            text="tag:unselected",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        )
        self.lbl_tag_title.pack(side="left")

        self.btn_delete_tag = ctk.CTkButton(
            header_f,
            text="🗑️ Delete Tag",
            fg_color=("#fee2e2", "#7f1d1d"),
            text_color=("#ef4444", "#fecaca"),
            hover_color=("#fecaca", "#991b1b"),
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            width=110,
            command=self.delete_tag
        )
        self.btn_delete_tag.pack(side="right", padx=5)

        self.btn_rename_tag = ctk.CTkButton(
            header_f,
            text="✏️ Rename",
            fg_color=("#e2e8f0", "#334155"),
            text_color=("#1e293b", "#f8fafc"),
            hover_color=("#cbd5e1", "#475569"),
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            width=90,
            command=self.rename_tag
        )
        self.btn_rename_tag.pack(side="right", padx=5)

        # 2. Owners Card
        self.f_owners = ctk.CTkFrame(
            self.tag_inspector_frame,
            fg_color=("#ffffff", "#1e293b"),
            border_width=1,
            border_color=("#e2e8f0", "#334155")
        )
        self.f_owners.pack(fill="x", pady=10)

        ctk.CTkLabel(
            self.f_owners,
            text="👥 Tag Owners (Groups & Autogroups)",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 8))

        self.owners_chips_frame = ctk.CTkFrame(self.f_owners, fg_color="transparent")
        self.owners_chips_frame.pack(fill="x", padx=15, pady=5)

        # Add Owner Row
        add_owner_f = ctk.CTkFrame(self.f_owners, fg_color="transparent")
        add_owner_f.pack(fill="x", padx=15, pady=(5, 15))

        self.combo_owners_list = ctk.CTkComboBox(
            add_owner_f,
            width=220,
            fg_color=("#f1f5f9", "#0f172a"),
            border_color=("#cbd5e1", "#334155")
        )
        self.combo_owners_list.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            add_owner_f,
            text="+ Add Owner",
            width=100,
            fg_color=("#3b82f6", "#2563eb"),
            hover_color=("#2563eb", "#1d4ed8"),
            text_color="white",
            command=self.add_owner_direct
        ).pack(side="left")

        # 3. Outbound Access Card
        self.f_outbound = ctk.CTkFrame(
            self.tag_inspector_frame,
            fg_color=("#ffffff", "#1e293b"),
            border_width=1,
            border_color=("#e2e8f0", "#334155")
        )
        self.f_outbound.pack(fill="both", expand=True, pady=10)

        outbound_header = ctk.CTkFrame(self.f_outbound, fg_color="transparent")
        outbound_header.pack(fill="x", padx=15, pady=(15, 8))

        ctk.CTkLabel(
            outbound_header,
            text="🏹 Outbound Access Rules",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            outbound_header,
            text="+ Add Outbound Rule",
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            text_color="white",
            command=self.add_outbound_rule,
            width=150
        ).pack(side="right")

        # Scrollable Rule rows
        self.outbound_rules_scroll = ctk.CTkScrollableFrame(self.f_outbound, fg_color="transparent")
        self.outbound_rules_scroll.pack(fill="both", expand=True, padx=10, pady=5)

    def setup_groups_tab(self):
        self.page_groups.grid_rowconfigure(1, weight=1)
        self.page_groups.grid_columnconfigure(0, weight=1)

        header_f = ctk.CTkFrame(self.page_groups, fg_color="transparent")
        header_f.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        ctk.CTkLabel(
            header_f,
            text="User Groups Manager",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
        ).pack(side="left")

        btn_add = ctk.CTkButton(
            header_f,
            text="+ Create New Group",
            fg_color=("#3b82f6", "#2563eb"),
            hover_color=("#2563eb", "#1d4ed8"),
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.add_group
        )
        btn_add.pack(side="right")

        self.groups_grid_scrollable = ctk.CTkScrollableFrame(self.page_groups, fg_color="transparent")
        self.groups_grid_scrollable.grid(row=1, column=0, sticky="nsew")

    def setup_devices_tab(self):
        self.page_devices.grid_rowconfigure(1, weight=1)
        self.page_devices.grid_columnconfigure(0, weight=1)

        header_f = ctk.CTkFrame(self.page_devices, fg_color="transparent")
        header_f.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        ctk.CTkLabel(
            header_f,
            text="Connected Live Devices",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
        ).pack(side="left")

        btn_fetch = ctk.CTkButton(
            header_f,
            text="🔄 Fetch Live Status (CLI)",
            fg_color=("#3b82f6", "#2563eb"),
            hover_color=("#2563eb", "#1d4ed8"),
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.fetch_devices_interactive
        )
        btn_fetch.pack(side="right", padx=(10, 0))

        # Search Bar filter
        self.device_search_var = tk.StringVar()
        self.device_search_var.trace_add("write", lambda *args: self.refresh_devices_table())

        search_entry = ctk.CTkEntry(
            header_f,
            placeholder_text="🔍 Filter devices...",
            textvariable=self.device_search_var,
            width=250,
            fg_color=("#f1f5f9", "#0f172a"),
            border_color=("#cbd5e1", "#334155")
        )
        search_entry.pack(side="right")

        # Table Display Container
        self.devices_table_container = ctk.CTkFrame(
            self.page_devices,
            fg_color=("#ffffff", "#1e293b"),
            border_width=1,
            border_color=("#e2e8f0", "#334155")
        )
        self.devices_table_container.grid(row=1, column=0, sticky="nsew")
        self.devices_table_container.grid_rowconfigure(1, weight=1)
        self.devices_table_container.grid_columnconfigure(0, weight=1)

        # Headers Row
        headers_f = ctk.CTkFrame(self.devices_table_container, fg_color=("#f1f5f9", "#0f172a"), height=40)
        headers_f.grid(row=0, column=0, sticky="ew")
        headers_f.pack_propagate(False)

        cols = [
            ("Status", 90),
            ("Hostname", 200),
            ("IP Address", 150),
            ("OS", 100),
            ("Assigned Badges / Owners", 300)
        ]

        for col_name, width in cols:
            f_col = ctk.CTkFrame(headers_f, width=width, fg_color="transparent")
            f_col.pack(side="left", fill="both", padx=5)
            f_col.pack_propagate(False)

            lbl = ctk.CTkLabel(
                f_col,
                text=col_name,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=("#475569", "#94a3b8")
            )
            if col_name in ["Status", "OS"]:
                lbl.pack(expand=True)
            else:
                lbl.pack(side="left", fill="y", padx=5)

        # Scrollable rows
        self.devices_scrollable = ctk.CTkScrollableFrame(self.devices_table_container, fg_color="transparent")
        self.devices_scrollable.grid(row=1, column=0, sticky="nsew")

    def setup_raw_tab(self):
        self.page_raw.grid_rowconfigure(1, weight=1)
        self.page_raw.grid_columnconfigure(0, weight=1)

        header_f = ctk.CTkFrame(self.page_raw, fg_color="transparent")
        header_f.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        ctk.CTkLabel(
            header_f,
            text="Raw Configuration JSON",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
        ).pack(side="left")

        btn_apply = ctk.CTkButton(
            header_f,
            text="✔️ Apply Changes",
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            command=self.apply_raw
        )
        btn_apply.pack(side="right", padx=(10, 0))

        btn_copy = ctk.CTkButton(
            header_f,
            text="📋 Copy JSON",
            fg_color=("#e2e8f0", "#334155"),
            text_color=("#1e293b", "#f8fafc"),
            hover_color=("#cbd5e1", "#475569"),
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            command=self.copy_raw_to_clipboard
        )
        btn_copy.pack(side="right", padx=(10, 0))

        btn_format = ctk.CTkButton(
            header_f,
            text="✨ Format JSON",
            fg_color=("#e2e8f0", "#334155"),
            text_color=("#1e293b", "#f8fafc"),
            hover_color=("#cbd5e1", "#475569"),
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            command=self.format_raw_json
        )
        btn_format.pack(side="right")

        # JSON text box box panel
        container = ctk.CTkFrame(
            self.page_raw,
            fg_color=("#ffffff", "#1e293b"),
            border_width=1,
            border_color=("#e2e8f0", "#334155")
        )
        container.grid(row=1, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.txt_raw = ctk.CTkTextbox(container, font=("Consolas", 13), fg_color="transparent")
        self.txt_raw.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def setup_topology_tab(self):
        self.page_topology.grid_rowconfigure(0, weight=1)
        self.page_topology.grid_columnconfigure(0, weight=1)

        self.topology_editor = TopologyEditor(
            self.page_topology,
            self.acl_data,
            refresh_callback=self.on_topology_edited
        )
        self.topology_editor.grid(row=0, column=0, sticky="nsew")
        self.topology_editor.load_data(self.acl_data, self.current_filepath)

    def on_topology_edited(self):
        self.refresh_ui(refresh_topology=False)

    # ---- PARSERS & UTILS ----
    def get_all_tags(self):
        return sorted(list(self.acl_data.get("tagOwners", {}).keys()))

    def get_all_groups(self):
        g = sorted(list(self.acl_data.get("groups", {}).keys()))
        g.extend(
            [
                "autogroup:admin",
                "autogroup:member",
                "autogroup:internet",
                "autogroup:shared",
            ]
        )
        return g

    # ---- REFRESH / DATA PIPELINE SYNCS ----
    def refresh_ui(self, refresh_topology=True):
        self.sort_rules()

        # 1. Network tag selection panel states sync
        self.refresh_tags_list()
        all_tags = self.get_all_tags()
        if self.current_tag and self.current_tag not in all_tags:
            self.current_tag = None

        if not self.current_tag:
            self.tag_inspector_frame.pack_forget()
            self.tag_empty_frame.pack(fill="both", expand=True)
        else:
            self.select_tag(self.current_tag)

        # 2. Access Rules Builder Table list sync
        self.refresh_rules()

        # 3. User Group manager Cards grid list sync
        self.refresh_groups()

        # 4. Live Devices Table list sync
        self.refresh_devices_table()

        # 5. Raw JSON editor sync
        self.txt_raw.delete("0.0", "end")
        self.txt_raw.insert("0.0", json.dumps(self.acl_data, indent=4))

        # 6. System overview statistics calculations sync
        self.refresh_overview_stats()

        # 7. Topology visual canvas update sync
        if refresh_topology and hasattr(self, "topology_editor"):
            self.topology_editor.load_data(self.acl_data, self.current_filepath)

    def sort_rules(self):
        """Reorder ACLs so specific rules come first, member-allow-all comes last."""
        acls = self.acl_data.get("acls", [])
        member_allow_all = None
        filtered = []
        for r in acls:
            src = r.get("src", [])
            dst = r.get("dst", [])
            if src == ["autogroup:member"] and dst == ["autogroup:member:*"]:
                member_allow_all = r
            else:
                filtered.append(r)
        if member_allow_all is not None:
            filtered.append(member_allow_all)
        self.acl_data["acls"] = filtered

    def refresh_overview_stats(self):
        num_acls = len(self.acl_data.get("acls", []))
        num_tags = len(self.get_all_tags())
        num_groups = len(self.acl_data.get("groups", {}))

        total_members = sum(len(users) for users in self.acl_data.get("groups", {}).values())

        devices = []
        if hasattr(self, "cli_devices") and self.cli_devices:
            devices = self.cli_devices
        elif hasattr(self, "topology_editor"):
            devices = self.topology_editor.get_devices_list()
        num_devices = len(devices)

        self.card_rules["num"].configure(text=f"{num_acls} Rules")
        self.card_tags["num"].configure(text=f"{num_tags} Tags")
        self.card_groups["num"].configure(text=f"{num_groups} Groups")
        self.card_devices["num"].configure(text=f"{num_devices} Devices")

        # Configuration metadata labels updates
        if self.current_filepath:
            fn = os.path.basename(self.current_filepath)
            self.lbl_overview_subtitle.configure(text=f"Configuration profile: {fn}")
            self.meta_labels["file_path"].configure(text=self.current_filepath)
        else:
            self.lbl_overview_subtitle.configure(text="Default Scratch / Unsaved Sandbox Workspace")
            self.meta_labels["file_path"].configure(text="Default Scratch space / Unsaved profile")

        self.meta_labels["rule_count"].configure(text=str(num_acls))
        self.meta_labels["tag_count"].configure(text=str(num_tags))
        self.meta_labels["group_count"].configure(text=str(num_groups))
        self.meta_labels["user_count"].configure(text=str(total_members))
        self.meta_labels["device_count"].configure(text=str(num_devices))
        self.meta_labels["status"].configure(text="Synchronized & Operational" if self.current_filepath else "Scratch Editor Mode")

    def refresh_rules(self):
        # Clean current rows
        for widget in self.rules_scrollable.winfo_children():
            widget.destroy()

        acls = self.acl_data.get("acls", [])
        if not acls:
            empty_lbl = ctk.CTkLabel(
                self.rules_scrollable,
                text="No Access Control Rules defined yet.\nClick '+ Add Access Rule' to create one.",
                font=ctk.CTkFont(family="Segoe UI", size=13, slant="italic"),
                text_color=("#64748b", "#94a3b8"),
                pady=40
            )
            empty_lbl.pack(fill="x")
            return

        for idx, r in enumerate(acls):
            row_frame = ctk.CTkFrame(
                self.rules_scrollable,
                fg_color=("#ffffff", "#1e293b") if idx % 2 == 0 else ("#f8fafc", "#162031"),
                height=45
            )
            row_frame.pack(fill="x", pady=2)
            row_frame.pack_propagate(False)

            # 1. ID Column
            f_id = ctk.CTkFrame(row_frame, width=60, fg_color="transparent")
            f_id.pack(side="left", fill="both", padx=5)
            f_id.pack_propagate(False)
            ctk.CTkLabel(f_id, text=f"#{idx}", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(expand=True)

            # 2. Source Column
            f_src = ctk.CTkFrame(row_frame, width=230, fg_color="transparent")
            f_src.pack(side="left", fill="both", padx=5)
            f_src.pack_propagate(False)

            src_str = ", ".join(r.get("src", []))
            chip_color = ("#e0e7ff", "#2a3b5c")
            text_color = ("#4338ca", "#a5b4fc")
            icon_prefix = ""

            if src_str.startswith("group:"):
                chip_color = ("#f3e8ff", "#3b2a5c")
                text_color = ("#6b21a8", "#d8b4fe")
                icon_prefix = "👥 "
            elif src_str.startswith("tag:"):
                chip_color = ("#ffedd5", "#5c3a21")
                text_color = ("#9a3412", "#ffb088")
                icon_prefix = "🏷️ "
            elif "@" in src_str:
                chip_color = ("#e0f2fe", "#1e3b5a")
                text_color = ("#0369a1", "#bae6fd")
                icon_prefix = "👤 "

            chip = ctk.CTkFrame(f_src, fg_color=chip_color, corner_radius=6)
            chip.pack(side="left", padx=5, pady=8)
            ctk.CTkLabel(
                chip,
                text=f"{icon_prefix}{src_str}",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=text_color,
                padx=8
            ).pack()

            # 3. Arrow Column
            f_dir = ctk.CTkFrame(row_frame, width=80, fg_color="transparent")
            f_dir.pack(side="left", fill="both", padx=5)
            f_dir.pack_propagate(False)
            ctk.CTkLabel(f_dir, text="➔", font=ctk.CTkFont(size=14), text_color=("#10b981", "#34d399")).pack(expand=True)

            # 4. Destination Column
            f_dst = ctk.CTkFrame(row_frame, width=230, fg_color="transparent")
            f_dst.pack(side="left", fill="both", padx=5)
            f_dst.pack_propagate(False)

            dst_raw = ", ".join(r.get("dst", []))
            dst_target, dst_ports = dst_raw.rsplit(":", 1) if ":" in dst_raw else (dst_raw, "*")

            dst_chip_color = ("#ffedd5", "#5c3a21")
            dst_text_color = ("#9a3412", "#ffb088")
            dst_icon = "🏷️ "
            if dst_target == "*":
                dst_chip_color = ("#e2e8f0", "#334155")
                dst_text_color = ("#475569", "#cbd5e1")
                dst_icon = "🌐 "

            dst_chip = ctk.CTkFrame(f_dst, fg_color=dst_chip_color, corner_radius=6)
            dst_chip.pack(side="left", padx=5, pady=8)
            ctk.CTkLabel(
                dst_chip,
                text=f"{dst_icon}{dst_target}",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=dst_text_color,
                padx=8
            ).pack()

            # 5. Ports Column
            f_ports = ctk.CTkFrame(row_frame, width=140, fg_color="transparent")
            f_ports.pack(side="left", fill="both", padx=5)
            f_ports.pack_propagate(False)

            port_box = ctk.CTkFrame(
                f_ports,
                fg_color=("#f1f5f9", "#0f172a"),
                corner_radius=4,
                border_width=1,
                border_color=("#cbd5e1", "#334155")
            )
            port_box.pack(side="left", padx=5, pady=8)
            ctk.CTkLabel(
                port_box,
                text=dst_ports,
                font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                text_color=("#475569", "#94a3b8"),
                padx=6
            ).pack()

            # 6. Actions Column
            f_act = ctk.CTkFrame(row_frame, width=120, fg_color="transparent")
            f_act.pack(side="left", fill="both", padx=5)
            f_act.pack_propagate(False)

            btn_sub = ctk.CTkFrame(f_act, fg_color="transparent")
            btn_sub.pack(expand=True)

            btn_edit = ctk.CTkButton(
                btn_sub,
                text="✏️",
                width=30,
                height=26,
                fg_color=("#e2e8f0", "#334155"),
                text_color=("#1e293b", "#f8fafc"),
                hover_color=("#cbd5e1", "#475569"),
                command=lambda idx=idx: self.edit_rule_by_index(idx)
            )
            btn_edit.pack(side="left", padx=4)

            btn_del = ctk.CTkButton(
                btn_sub,
                text="🗑️",
                width=30,
                height=26,
                fg_color=("#fee2e2", "#7f1d1d"),
                text_color=("#ef4444", "#fecaca"),
                hover_color=("#fecaca", "#991b1b"),
                command=lambda idx=idx: self.delete_rule_by_index(idx)
            )
            btn_del.pack(side="left", padx=4)

    def refresh_tags_list(self):
        for widget in self.tags_scrollable.winfo_children():
            widget.destroy()

        search_term = self.tag_search_var.get().lower().strip()
        tags = self.get_all_tags()

        filtered_tags = [t for t in tags if search_term in t.lower()]

        for t in filtered_tags:
            is_active = (self.current_tag == t)

            btn = ctk.CTkButton(
                self.tags_scrollable,
                text=f"🏷️  {t.replace('tag:', '')}",
                anchor="w",
                fg_color=("#3b82f6", "#2563eb") if is_active else "transparent",
                text_color="white" if is_active else ("#1e293b", "#cbd5e1"),
                hover_color=("#e2e8f0", "#1e293b") if not is_active else None,
                font=ctk.CTkFont(family="Segoe UI", weight="bold" if is_active else "normal"),
                command=lambda name=t: self.select_tag(name),
            )
            btn.pack(fill="x", pady=2)

    def refresh_groups(self):
        for widget in self.groups_grid_scrollable.winfo_children():
            widget.destroy()

        groups_dict = self.acl_data.get("groups", {})
        if not groups_dict:
            empty_lbl = ctk.CTkLabel(
                self.groups_grid_scrollable,
                text="No user groups defined yet.\nClick '+ Create New Group' at the top to configure.",
                font=ctk.CTkFont(family="Segoe UI", size=13, slant="italic"),
                text_color=("#64748b", "#94a3b8"),
                pady=40
            )
            empty_lbl.pack(fill="x")
            return

        grid_container = ctk.CTkFrame(self.groups_grid_scrollable, fg_color="transparent")
        grid_container.pack(fill="both", expand=True)
        grid_container.grid_columnconfigure((0, 1), weight=1, uniform="group_cards")

        groups_list = sorted(list(groups_dict.keys()))
        for idx, g in enumerate(groups_list):
            row = idx // 2
            col = idx % 2

            card = ctk.CTkFrame(
                grid_container,
                fg_color=("#ffffff", "#1e293b"),
                border_width=1,
                border_color=("#e2e8f0", "#334155"),
                corner_radius=8
            )
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            # Header info
            g_header = ctk.CTkFrame(card, fg_color=("#f1f5f9", "#0f172a"), height=40)
            g_header.pack(fill="x")
            g_header.pack_propagate(False)

            accent = ctk.CTkFrame(g_header, width=4, fg_color="#8b5cf6")
            accent.pack(side="left", fill="y")

            lbl_title = ctk.CTkLabel(g_header, text=g, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), padx=10)
            lbl_title.pack(side="left")

            btn_del = ctk.CTkButton(
                g_header,
                text="🗑️",
                width=24,
                height=24,
                fg_color="transparent",
                text_color="#ef4444",
                hover_color=("#fee2e2", "#7f1d1d"),
                font=ctk.CTkFont(size=12),
                command=lambda g_name=g: self.delete_group_direct(g_name)
            )
            btn_del.pack(side="right", padx=6)

            btn_rename = ctk.CTkButton(
                g_header,
                text="✏️",
                width=24,
                height=24,
                fg_color="transparent",
                text_color=("#475569", "#cbd5e1"),
                hover_color=("#cbd5e1", "#334155"),
                font=ctk.CTkFont(size=12),
                command=lambda g_name=g: self.rename_group_direct(g_name)
            )
            btn_rename.pack(side="right", padx=2)

            # Member listing body
            users = groups_dict.get(g, [])

            users_frame = ctk.CTkFrame(card, fg_color="transparent")
            users_frame.pack(fill="both", expand=True, padx=12, pady=12)

            if not users:
                empty_user_lbl = ctk.CTkLabel(
                    users_frame,
                    text="No users in group",
                    font=ctk.CTkFont(slant="italic"),
                    text_color=("#94a3b8", "#64748b")
                )
                empty_user_lbl.pack(pady=10)
            else:
                for u in users:
                    u_row = ctk.CTkFrame(users_frame, fg_color="transparent", height=28)
                    u_row.pack(fill="x", pady=2)
                    u_row.pack_propagate(False)

                    ctk.CTkLabel(u_row, text=f"👤  {u}", font=ctk.CTkFont(family="Segoe UI", size=12), anchor="w").pack(side="left", fill="both", expand=True)

                    btn_rem_user = ctk.CTkButton(
                        u_row,
                        text="×",
                        width=18,
                        height=18,
                        fg_color="transparent",
                        text_color="#ef4444",
                        hover_color=("#fee2e2", "#7f1d1d"),
                        font=ctk.CTkFont(size=11, weight="bold"),
                        command=lambda g_name=g, u_name=u: self.remove_user_from_group_direct(g_name, u_name)
                    )
                    btn_rem_user.pack(side="right")

            # Input footer bar
            g_footer = ctk.CTkFrame(card, fg_color="transparent")
            g_footer.pack(fill="x", padx=12, pady=(0, 12))

            entry_user = ctk.CTkEntry(
                g_footer,
                placeholder_text="Enter user email...",
                height=28,
                fg_color=("#f1f5f9", "#0f172a"),
                border_color=("#cbd5e1", "#334155")
            )
            entry_user.pack(side="left", fill="x", expand=True, padx=(0, 6))

            btn_add_user = ctk.CTkButton(
                g_footer,
                text="Add",
                width=50,
                height=28,
                fg_color=("#8b5cf6", "#7c3aed"),
                hover_color=("#7c3aed", "#6d28d9"),
                text_color="white",
                command=lambda g_name=g, ent=entry_user: self.add_user_to_group_direct(g_name, ent)
            )
            btn_add_user.pack(side="right")

    def refresh_devices_table(self):
        for widget in self.devices_scrollable.winfo_children():
            widget.destroy()

        devices = []
        if hasattr(self, "cli_devices") and self.cli_devices:
            devices = self.cli_devices
        elif hasattr(self, "topology_editor"):
            devices = self.topology_editor.get_devices_list()

        if not devices:
            empty_lbl = ctk.CTkLabel(
                self.devices_scrollable,
                text="No device configurations cached.\nVerify 'Tailscale Devices.md' exists, or query using the live command above.",
                font=ctk.CTkFont(family="Segoe UI", size=13, slant="italic"),
                text_color=("#64748b", "#94a3b8"),
                pady=40
            )
            empty_lbl.pack(fill="x")
            return

        search_term = self.device_search_var.get().lower().strip()

        filtered_devices = []
        for dev in devices:
            hostname = dev.get("hostname", "")
            ips = dev.get("ips", [""])
            ip = ips[0] if ips else ""
            os_name = dev.get("os", "")
            owner = dev.get("owner", "")
            tags = dev.get("tags", [])

            match = (
                search_term in hostname.lower() or
                search_term in ip.lower() or
                search_term in os_name.lower() or
                search_term in owner.lower() or
                any(search_term in t.lower() for t in tags)
            )

            if match or not search_term:
                filtered_devices.append(dev)

        if not filtered_devices:
            empty_lbl = ctk.CTkLabel(
                self.devices_scrollable,
                text="No devices match your search parameters.",
                font=ctk.CTkFont(family="Segoe UI", size=13, slant="italic"),
                text_color=("#64748b", "#94a3b8"),
                pady=20
            )
            empty_lbl.pack(fill="x")
            return

        for idx, dev in enumerate(filtered_devices):
            row_frame = ctk.CTkFrame(
                self.devices_scrollable,
                fg_color=("#ffffff", "#1e293b") if idx % 2 == 0 else ("#f8fafc", "#162031"),
                height=45
            )
            row_frame.pack(fill="x", pady=2)
            row_frame.pack_propagate(False)

            # 1. Status Indicator Dot
            f_status = ctk.CTkFrame(row_frame, width=90, fg_color="transparent")
            f_status.pack(side="left", fill="both", padx=5)
            f_status.pack_propagate(False)

            status = dev.get("status", "Offline").lower()
            is_active = "active" in status or status == "-"
            status_color = "#10b981" if is_active else "#64748b"
            status_text = "Active" if is_active else "Offline"

            ind_sub = ctk.CTkFrame(f_status, fg_color="transparent")
            ind_sub.pack(expand=True)
            ctk.CTkLabel(ind_sub, text="●", text_color=status_color, font=ctk.CTkFont(size=14)).pack(side="left")
            ctk.CTkLabel(
                ind_sub,
                text=status_text,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=status_color,
                padx=4
            ).pack(side="left")

            # 2. Hostname
            f_host = ctk.CTkFrame(row_frame, width=200, fg_color="transparent")
            f_host.pack(side="left", fill="both", padx=5)
            f_host.pack_propagate(False)
            ctk.CTkLabel(
                f_host,
                text=dev.get("hostname"),
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                anchor="w"
            ).pack(side="left", fill="both", expand=True)

            # 3. IP Address
            f_ip = ctk.CTkFrame(row_frame, width=150, fg_color="transparent")
            f_ip.pack(side="left", fill="both", padx=5)
            f_ip.pack_propagate(False)
            ctk.CTkLabel(
                f_ip,
                text=dev.get("ips", [""])[0],
                font=ctk.CTkFont(family="Consolas", size=12),
                anchor="w",
                text_color=("#475569", "#94a3b8")
            ).pack(side="left", fill="both", expand=True)

            # 4. OS Column
            f_os = ctk.CTkFrame(row_frame, width=100, fg_color="transparent")
            f_os.pack(side="left", fill="both", padx=5)
            f_os.pack_propagate(False)
            ctk.CTkLabel(f_os, text=dev.get("os", "Unknown").capitalize(), font=ctk.CTkFont(family="Segoe UI", size=11)).pack(expand=True)

            # 5. Badges/Owners Column
            f_tags = ctk.CTkFrame(row_frame, width=300, fg_color="transparent")
            f_tags.pack(side="left", fill="both", padx=5)
            f_tags.pack_propagate(False)

            chips_c = ctk.CTkFrame(f_tags, fg_color="transparent")
            chips_c.pack(side="left", fill="y", pady=5)

            dev_tags = dev.get("tags", [])
            owner = dev.get("owner", "")

            if dev_tags:
                for t in dev_tags:
                    t_chip = ctk.CTkFrame(chips_c, fg_color=("#ffedd5", "#5c3a21"), corner_radius=5)
                    t_chip.pack(side="left", padx=2, pady=3)
                    ctk.CTkLabel(
                        t_chip,
                        text=t.replace("tag:", "🏷️ "),
                        font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                        text_color=("#9a3412", "#ffb088"),
                        padx=5
                    ).pack()
            elif owner:
                o_chip = ctk.CTkFrame(chips_c, fg_color=("#e0f2fe", "#1e3b5a"), corner_radius=5)
                o_chip.pack(side="left", padx=2, pady=3)
                ctk.CTkLabel(
                    o_chip,
                    text=f"👤 {owner}",
                    font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                    text_color=("#0369a1", "#bae6fd"),
                    padx=5
                ).pack()
            else:
                ctk.CTkLabel(
                    chips_c,
                    text="Untagged / Unowned device",
                    font=ctk.CTkFont(family="Segoe UI", size=10, slant="italic"),
                    text_color=("#64748b", "#94a3b8")
                ).pack(side="left", fill="y")

            btn_manage = ctk.CTkButton(
                f_tags,
                text="🔑",
                width=28,
                height=28,
                fg_color="transparent",
                text_color=("#475569", "#cbd5e1"),
                hover_color=("#cbd5e1", "#334155"),
                font=ctk.CTkFont(size=14),
                command=lambda dev_name=dev.get("hostname"): self.manage_device_tag_owners(dev_name)
            )
            btn_manage.pack(side="right", padx=5, pady=8)

    # ---- TAG INSPECTOR ACTIONS ----
    def select_tag(self, tag):
        self.current_tag = tag

        # Show inspector frame, hide empty state
        self.tag_empty_frame.pack_forget()
        self.tag_inspector_frame.pack(fill="both", expand=True)

        self.lbl_tag_title.configure(text=tag)

        # Highlight tag selection
        self.refresh_tags_list()

        # Update owners chips
        for widget in self.owners_chips_frame.winfo_children():
            widget.destroy()

        owners = self.acl_data.get("tagOwners", {}).get(tag, [])
        if not owners:
            ctk.CTkLabel(
                self.owners_chips_frame,
                text="No owners defined. This tag is currently orphaned.",
                font=ctk.CTkFont(slant="italic"),
                text_color="#ef4444"
            ).pack(side="left")
        else:
            for o in owners:
                chip = ctk.CTkFrame(self.owners_chips_frame, fg_color=("#f3e8ff", "#3b2a5c"), corner_radius=6)
                chip.pack(side="left", padx=4, pady=4)

                disp_owner = o.replace("group:", "👥 ").replace("autogroup:", "⚙️ ")
                ctk.CTkLabel(
                    chip,
                    text=disp_owner,
                    font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                    text_color=("#6b21a8", "#d8b4fe"),
                    padx=8
                ).pack(side="left")

                btn_del = ctk.CTkButton(
                    chip,
                    text="×",
                    width=16,
                    height=16,
                    fg_color="transparent",
                    text_color=("#6b21a8", "#d8b4fe"),
                    hover_color=("#e9d5ff", "#581c87"),
                    font=ctk.CTkFont(size=12, weight="bold"),
                    command=lambda name=o: self.remove_owner_direct(name)
                )
                btn_del.pack(side="left", padx=(0, 4))

        # Re-populate add owner combo field dropdown options
        all_possible = self.get_all_groups()
        available = [x for x in all_possible if x not in owners]
        if available:
            self.combo_owners_list.configure(values=available)
            self.combo_owners_list.set(available[0])
        else:
            self.combo_owners_list.configure(values=["All groups are owners"])
            self.combo_owners_list.set("All groups are owners")

        # Update outbound rules scroll container rows
        for widget in self.outbound_rules_scroll.winfo_children():
            widget.destroy()

        outbound_rules = []
        for i, r in enumerate(self.acl_data.get("acls", [])):
            if tag in r.get("src", []):
                outbound_rules.append((i, r))

        if not outbound_rules:
            ctk.CTkLabel(
                self.outbound_rules_scroll,
                text="No outbound access rules originating from this tag.",
                font=ctk.CTkFont(slant="italic"),
                text_color=("#64748b", "#94a3b8"),
                pady=20
            ).pack(fill="x")
        else:
            for idx, r in outbound_rules:
                row_f = ctk.CTkFrame(self.outbound_rules_scroll, fg_color=("#ffffff", "#1e293b"), height=38)
                row_f.pack(fill="x", pady=2)
                row_f.pack_propagate(False)

                ctk.CTkLabel(
                    row_f,
                    text=f"Rule #{idx}",
                    font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                    width=70,
                    anchor="w",
                    padx=10
                ).pack(side="left")

                dst_raw = ", ".join(r.get("dst", []))
                dst_target, dst_ports = dst_raw.rsplit(":", 1) if ":" in dst_raw else (dst_raw, "*")

                dst_chip_color = ("#ffedd5", "#5c3a21")
                dst_text_color = ("#9a3412", "#ffb088")
                dst_icon = "🏷️ "
                if dst_target == "*":
                    dst_chip_color = ("#e2e8f0", "#334155")
                    dst_text_color = ("#475569", "#cbd5e1")
                    dst_icon = "🌐 "
                elif dst_target.startswith("group:"):
                    dst_chip_color = ("#f3e8ff", "#3b2a5c")
                    dst_text_color = ("#6b21a8", "#d8b4fe")
                    dst_icon = "👥 "

                dst_chip = ctk.CTkFrame(row_f, fg_color=dst_chip_color, corner_radius=6)
                dst_chip.pack(side="left", padx=5, pady=5)
                ctk.CTkLabel(
                    dst_chip,
                    text=f"{dst_icon}{dst_target}",
                    font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                    text_color=dst_text_color,
                    padx=6
                ).pack()

                port_box = ctk.CTkFrame(row_f, fg_color=("#f1f5f9", "#0f172a"), corner_radius=4, border_width=1, border_color=("#cbd5e1", "#334155"))
                port_box.pack(side="left", padx=5, pady=5)
                ctk.CTkLabel(
                    port_box,
                    text=dst_ports,
                    font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
                    text_color=("#475569", "#94a3b8"),
                    padx=5
                ).pack()

                btn_del = ctk.CTkButton(
                    row_f,
                    text="🗑️",
                    width=26,
                    height=24,
                    fg_color=("#fee2e2", "#7f1d1d"),
                    text_color=("#ef4444", "#fecaca"),
                    hover_color=("#fecaca", "#991b1b"),
                    command=lambda rule_id=idx: self.delete_rule_by_index(rule_id)
                )
                btn_del.pack(side="right", padx=10)

    def create_tag(self):
        d = ctk.CTkInputDialog(
            text="New tag name (we'll prepend 'tag:' automatically):", title="Create Tag"
        )
        tag = d.get_input()
        if tag:
            tag = tag.strip()
            if not tag.startswith("tag:"):
                tag = f"tag:{tag}"
            if "tagOwners" not in self.acl_data:
                self.acl_data["tagOwners"] = {}
            if tag not in self.acl_data["tagOwners"]:
                self.acl_data["tagOwners"][tag] = ["autogroup:admin"]
                self.refresh_ui()
                self.select_tag(tag)

    def rename_tag(self):
        if not self.current_tag:
            return
        old = self.current_tag
        short_old = old.replace("tag:", "")
        d = ctk.CTkInputDialog(text=f"Rename '{short_old}' to:", title="Rename Tag")
        new = d.get_input()
        if not new:
            return
        new = new.strip()
        if not new.startswith("tag:"):
            new = f"tag:{new}"
        if new == old:
            return

        owners = self.acl_data["tagOwners"].pop(old)
        self.acl_data["tagOwners"][new] = owners

        for r in self.acl_data.get("acls", []):
            if old in r.get("src", []):
                r["src"] = [new if s == old else s for s in r["src"]]

            new_dst = []
            for d_str in r.get("dst", []):
                if d_str.startswith(f"{old}:"):
                    new_dst.append(d_str.replace(f"{old}:", f"{new}:", 1))
                else:
                    new_dst.append(d_str)
            r["dst"] = new_dst

        self.rename_tag_in_devices_file(old, new)
        self.refresh_ui()
        self.select_tag(new)

    def delete_tag(self):
        if not self.current_tag:
            return
        t = self.current_tag
        if messagebox.askyesno(
            "Confirm Delete", f"Permanently delete {t} and all associated access rules?"
        ):
            self.acl_data["tagOwners"].pop(t, None)
            new_acls = []
            for r in self.acl_data.get("acls", []):
                if t in r.get("src", []):
                    continue
                r["dst"] = [d for d in r.get("dst", []) if not d.startswith(f"{t}:")]
                if r["dst"]:
                    new_acls.append(r)

            self.acl_data["acls"] = new_acls
            self.delete_tag_from_devices_file(t)
            self.current_tag = None
            self.refresh_ui()

    def add_owner_direct(self):
        if not self.current_tag:
            return
        val = self.combo_owners_list.get()
        if val and val != "All groups are owners":
            self.acl_data.setdefault("tagOwners", {}).setdefault(self.current_tag, [])
            if val not in self.acl_data["tagOwners"][self.current_tag]:
                self.acl_data["tagOwners"][self.current_tag].append(val)
                self.refresh_ui()
                self.select_tag(self.current_tag)

    def remove_owner_direct(self, owner):
        if not self.current_tag:
            return
        owners = self.acl_data.get("tagOwners", {}).get(self.current_tag, [])
        if owner in owners:
            if messagebox.askyesno("Confirm Remove", f"Remove '{owner}' as an owner of '{self.current_tag}'?"):
                self.acl_data["tagOwners"][self.current_tag].remove(owner)
                self.refresh_ui()
                self.select_tag(self.current_tag)

    def add_outbound_rule(self):
        if not self.current_tag:
            return
        opts = ["*"] + self.get_all_tags()
        d = CustomDialog(self, "Add Outbound Rule", ["Select Destination:"], [opts])
        if d.result:
            dst, port = d.result
            self.acl_data.setdefault("acls", []).append(
                {
                    "action": "accept",
                    "src": [self.current_tag],
                    "dst": [f"{dst}:{port}"],
                }
            )
            self.refresh_ui()
            self.select_tag(self.current_tag)

    # ---- RULE ACTIONS ----
    def create_custom_rule(self):
        srcs = ["*"] + self.get_all_tags() + self.get_all_groups()
        dsts = ["*"] + self.get_all_tags()
        d = CustomDialog(self, "Create Access Rule", ["Select Source:", "Select Destination:"], [srcs, dsts])
        if d.result:
            s, dst, p = d.result
            self.acl_data.setdefault("acls", []).append(
                {"action": "accept", "src": [s], "dst": [f"{dst}:{p}"]}
            )
            self.refresh_ui()

    def edit_rule_by_index(self, idx):
        try:
            r = self.acl_data.get("acls", [])[idx]
            old_src = r["src"][0]
            old_dst_str = r["dst"][0]
            old_dst, old_port = (
                old_dst_str.rsplit(":", 1) if ":" in old_dst_str else (old_dst_str, "*")
            )

            srcs = ["*"] + self.get_all_tags() + self.get_all_groups()
            dsts = ["*"] + self.get_all_tags()
            d = CustomDialog(
                self,
                f"Edit Rule #{idx}",
                ["Select Source:", "Select Destination:"],
                [srcs, dsts],
                default_values=[old_src, old_dst, old_port],
            )
            if d.result:
                s, dst, p = d.result
                r["src"] = [s]
                r["dst"] = [f"{dst}:{p}"]
                self.refresh_ui()
        except Exception as e:
            messagebox.showerror("Error", f"Could not edit rule: {e}")

    def delete_rule_by_index(self, idx):
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete Access Rule #{idx}?"):
            try:
                del self.acl_data["acls"][idx]
                self.refresh_ui()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete rule: {e}")

    # ---- GROUP MANAGER ACTIONS ----
    def add_group(self):
        d = ctk.CTkInputDialog(
            text="New Group Name (we'll prepend 'group:' automatically):", title="Create Group"
        )
        g = d.get_input()
        if g:
            g = g.strip()
            if not g.startswith("group:"):
                g = f"group:{g}"
            self.acl_data.setdefault("groups", {})[g] = []
            self.refresh_ui()

    def rename_group_direct(self, old_group):
        short_old = old_group.replace("group:", "")
        d = ctk.CTkInputDialog(text=f"Rename '{short_old}' to:", title="Rename Group")
        new = d.get_input()
        if new:
            new = new.strip()
            if not new.startswith("group:"):
                new = f"group:{new}"
            if new != old_group:
                users = self.acl_data["groups"].pop(old_group)
                self.acl_data["groups"][new] = users

                for t, o_list in self.acl_data.get("tagOwners", {}).items():
                    if old_group in o_list:
                        self.acl_data["tagOwners"][t] = [
                            new if x == old_group else x for x in o_list
                        ]
                for r in self.acl_data.get("acls", []):
                    if old_group in r.get("src", []):
                        r["src"] = [new if x == old_group else x for x in r["src"]]
                self.refresh_ui()

    def delete_group_direct(self, group_name):
        if messagebox.askyesno("Confirm Delete", f"Permanently delete group '{group_name}' and all associated references?"):
            self.acl_data["groups"].pop(group_name, None)
            for t, o_list in self.acl_data.get("tagOwners", {}).items():
                if group_name in o_list:
                    o_list.remove(group_name)
            self.acl_data["acls"] = [
                r
                for r in self.acl_data.get("acls", [])
                if group_name not in r.get("src", [])
            ]
            self.refresh_ui()

    def add_user_to_group_direct(self, group_name, entry_widget):
        val = entry_widget.get().strip()
        if val:
            if group_name in self.acl_data.setdefault("groups", {}):
                if val not in self.acl_data["groups"][group_name]:
                    self.acl_data["groups"][group_name].append(val)
                    entry_widget.delete(0, "end")
                    self.refresh_ui()

    def remove_user_from_group_direct(self, group_name, user_email):
        if group_name in self.acl_data.get("groups", {}):
            if user_email in self.acl_data["groups"][group_name]:
                if messagebox.askyesno("Confirm Remove", f"Remove user '{user_email}' from group '{group_name}'?"):
                    self.acl_data["groups"][group_name].remove(user_email)
                    self.refresh_ui()

    def manage_device_tag_owners(self, hostname):
        clean_hostname = hostname.split()[0] if hostname else ""
        devices = []
        if hasattr(self, "cli_devices") and self.cli_devices:
            devices.extend(self.cli_devices)
        if hasattr(self, "topology_editor"):
            devices.extend(self.topology_editor.get_devices_list())

        device = None
        for d in devices:
            d_host = d.get("hostname", "")
            d_clean = d_host.split()[0] if d_host else ""
            if d_clean == clean_hostname:
                device = d
                break

        if not device:
            messagebox.showerror("Error", f"Device '{hostname}' not found.")
            return

        device_tags = device.get("tags", [])
        all_groups = list(self.acl_data.get("groups", {}).keys())

        d = DeviceTagOwnersDialog(self, hostname, device_tags, self.acl_data, all_groups)
        if d.saved:
            self.refresh_ui()
            messagebox.showinfo("Success", f"Tag owners updated for device '{hostname}' tags.")

    # ---- DEVICE LIST ACTIONS ----
    def _build_md_tag_map(self):
        """Read Tailscale Devices.md and return {hostname_lower: [tag, ...]} for devices with tags."""
        tag_map = {}
        md_path = "Tailscale Devices.md"
        if not os.path.exists(md_path):
            return tag_map
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.startswith("|") or "IP Address" in line or "---" in line:
                        continue
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    # Columns: IP, Hostname, Owner, OS, Status, Tags
                    if len(parts) < 6:
                        continue
                    hostname = parts[1].split()[0].lower()
                    tags_raw = parts[5]
                    if not tags_raw or tags_raw == "-":
                        continue
                    tags = []
                    for t in tags_raw.split(","):
                        t = t.strip()
                        if not t or t == "-":
                            continue
                        if not t.startswith("tag:"):
                            t = f"tag:{t}"
                        tags.append(t)
                    if tags:
                        tag_map[hostname] = tags
        except Exception:
            pass
        return tag_map

    def fetch_devices_interactive(self):
        self.fetch_devices()
        self.refresh_devices_table()

    def fetch_devices(self):
        self.cli_devices = []
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                peers = data.get("Peer", {})
                self_node = data.get("Self", {})

                # Build UserID → LoginName lookup from the top-level User map
                user_map = data.get("User", {})

                def resolve_owner(node):
                    """Return a human-readable owner login name from the node's UserID."""
                    uid = node.get("UserID", node.get("User", 0))
                    if isinstance(uid, int) and uid != 0:
                        user_entry = user_map.get(str(uid), {})
                        login = user_entry.get("LoginName", "")
                        if login:
                            return login
                    # Fallback: if User is already a string (unlikely but safe)
                    if isinstance(uid, str) and uid:
                        return uid
                    return ""

                def parse_dev(node, label=""):
                    host = f"{node.get('HostName', 'Unknown')} ({label})" if label else node.get("HostName", "Unknown")
                    ips = node.get("TailscaleIPs", [""])
                    os_type = node.get("OS", "Unknown")
                    # Tags can be null in the JSON — normalize to an empty list
                    tags = node.get("Tags") or []
                    owner = resolve_owner(node)

                    return {
                        'hostname': host,
                        'ips': ips,
                        'owner': owner,
                        'os': os_type,
                        'status': 'Active' if node.get('Active', False) or label == "Self" else 'Offline',
                        'tags': tags
                    }

                self.cli_devices.append(parse_dev(self_node, "Self"))
                for v in peers.values():
                    self.cli_devices.append(parse_dev(v))

                # Enrich CLI devices that have no tags with data from the local MD file.
                # Tailscale CLI often returns "Tags": null even for tagged devices when
                # the ACL system manages tagging — the MD file acts as the source of truth.
                md_tag_map = self._build_md_tag_map()
                for dev in self.cli_devices:
                    if not dev.get("tags"):
                        # Strip the "(Self)" label suffix added by parse_dev
                        base_host = dev["hostname"].split(" (")[0].lower()
                        md_tags = md_tag_map.get(base_host, [])
                        if md_tags:
                            dev["tags"] = md_tags

                messagebox.showinfo("Success", f"Successfully loaded {len(self.cli_devices)} devices from Tailscale status CLI.")
            else:
                messagebox.showerror("CLI Error", f"Tailscale CLI execution failed with code {result.returncode}")
        except Exception as e:
            messagebox.showwarning("CLI Offline", f"Could not connect to Tailscale CLI status service: {e}\nDisplaying local workspace cache.")

    # ---- RAW JSON UTILS ----
    def copy_raw_to_clipboard(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.txt_raw.get("0.0", "end").strip())
            messagebox.showinfo("Clipboard", "JSON copied to clipboard successfully!")
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Could not copy: {e}")

    def format_raw_json(self):
        try:
            raw_text = self.txt_raw.get("0.0", "end")
            parsed = json5.loads(raw_text)
            formatted = json.dumps(parsed, indent=4)
            self.txt_raw.delete("0.0", "end")
            self.txt_raw.insert("0.0", formatted)
        except Exception as e:
            messagebox.showerror("JSON Syntax Error", f"Failed to parse text as valid JSON: {e}")

    def apply_raw(self):
        try:
            self.acl_data = json5.loads(self.txt_raw.get("0.0", "end"))
            self.refresh_ui()
        except Exception as e:
            messagebox.showerror("JSON Syntax Error", str(e))

    # ---- LOAD & SAVE PERSISTENCE ----
    def load_json(self):
        p = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if p:
            self.current_filepath = p
            with open(p, "r", encoding="utf-8") as f:
                self.acl_data = json5.loads(f.read())
            self.lbl_status.configure(text=f"Loaded Profile:\n{os.path.basename(p)}")

            # Cache latest loaded filepath config
            try:
                state_file = os.path.join(os.path.dirname(__file__), ".last_config.txt")
                with open(state_file, "w", encoding="utf-8") as f:
                    f.write(p)
            except Exception:
                pass

            self.refresh_ui()

    def validate_and_fix_tag_owners(self):
        """
        Scans all ACL rules and SSH rules for tag references.
        Any tag found that is not in tagOwners is automatically added
        with 'autogroup:admin' as the default owner.
        Returns a list of tags that were auto-added (empty list if none).
        """
        tag_owners = self.acl_data.setdefault("tagOwners", {})
        referenced_tags = set()

        # Collect tags from ACL rules (src and dst)
        for rule in self.acl_data.get("acls", []):
            for src in rule.get("src", []):
                if src.startswith("tag:"):
                    referenced_tags.add(src)
            for dst in rule.get("dst", []):
                # dst can be "tag:name:port" or "tag:name:*", strip the port
                parts = dst.split(":")
                if len(parts) >= 2 and parts[0] == "tag":
                    referenced_tags.add(f"tag:{parts[1]}")

        # Collect tags from SSH rules (dst)
        for rule in self.acl_data.get("ssh", []):
            for src in rule.get("src", []):
                if src.startswith("tag:"):
                    referenced_tags.add(src)
            for dst in rule.get("dst", []):
                if dst.startswith("tag:"):
                    referenced_tags.add(dst)

        # Find any missing tags
        auto_added = []
        for tag in sorted(referenced_tags):
            if tag not in tag_owners:
                tag_owners[tag] = ["autogroup:admin"]
                auto_added.append(tag)

        return auto_added

    def save_json(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON Files", "*.json")]
        )
        if p:
            self.current_filepath = p
            self.apply_raw()

            # Auto-fix any tags referenced in rules but missing from tagOwners
            auto_added = self.validate_and_fix_tag_owners()
            if auto_added:
                tag_list = "\n  • " + "\n  • ".join(auto_added)
                messagebox.showwarning(
                    "Auto-Fixed Missing Tag Owners",
                    f"The following tags were referenced in rules but missing from tagOwners. "
                    f"They have been automatically added with 'autogroup:admin' as the default owner:{tag_list}\n\n"
                    f"You can manage their owners in the Network Tags panel."
                )
                self.refresh_ui()

            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.acl_data, f, indent=4)
            self.lbl_status.configure(text=f"Saved Profile:\n{os.path.basename(p)}")

            try:
                state_file = os.path.join(os.path.dirname(__file__), ".last_config.txt")
                with open(state_file, "w", encoding="utf-8") as f:
                    f.write(p)
            except Exception:
                pass

            messagebox.showinfo("Success", "Configuration saved successfully!")

    def autoload_last_config(self):
        try:
            state_file = os.path.join(os.path.dirname(__file__), ".last_config.txt")
            if os.path.exists(state_file):
                with open(state_file, "r", encoding="utf-8") as f:
                    p = f.read().strip()
                if p and os.path.exists(p):
                    self.current_filepath = p
                    with open(p, "r", encoding="utf-8") as f:
                        self.acl_data = json5.loads(f.read())
                    self.lbl_status.configure(text=f"Loaded Profile:\n{os.path.basename(p)}")
                    self.refresh_ui()
        except Exception as e:
            print(f"Error autoloading last config profile: {e}")

    # ---- AI ASSISTANT CHATBOT ----
    def setup_chatbot_page(self):
        self.page_chatbot.grid_rowconfigure(1, weight=1)
        self.page_chatbot.grid_columnconfigure(0, weight=1)

        # 1. Top Bar Control Frame
        top_bar = ctk.CTkFrame(self.page_chatbot, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        ctk.CTkLabel(
            top_bar,
            text="Tailscale AI Assistant (Ollama)",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
        ).pack(side="left")

        # Models Dropdown
        self.combo_models = ctk.CTkComboBox(
            top_bar,
            values=["qwen3.6:35b-a3b", "qwen2.5-coder:7b", "deepseek-r1:70b", "gemma4:31b"],
            width=220,
            fg_color=("#f1f5f9", "#0f172a"),
            border_color=("#cbd5e1", "#334155")
        )
        self.combo_models.pack(side="right", padx=(10, 0))
        self.combo_models.set("qwen3.6:35b-a3b")

        # Clear Chat Button
        btn_clear = ctk.CTkButton(
            top_bar,
            text="🗑️ Clear Chat",
            fg_color=("#fee2e2", "#7f1d1d"),
            text_color=("#ef4444", "#fecaca"),
            hover_color=("#fecaca", "#991b1b"),
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            width=100,
            command=self.clear_chat
        )
        btn_clear.pack(side="right", padx=(10, 0))

        # Fetch Models Button
        btn_fetch_models = ctk.CTkButton(
            top_bar,
            text="🔄 Scan Models",
            fg_color=("#e2e8f0", "#334155"),
            text_color=("#1e293b", "#f8fafc"),
            hover_color=("#cbd5e1", "#475569"),
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            width=110,
            command=self.fetch_ollama_models
        )
        btn_fetch_models.pack(side="right")

        # 2. Chat Scroll History Container
        self.chat_container = ctk.CTkFrame(
            self.page_chatbot,
            fg_color=("#ffffff", "#1e293b"),
            border_width=1,
            border_color=("#e2e8f0", "#334155")
        )
        self.chat_container.grid(row=1, column=0, sticky="nsew")
        self.chat_container.grid_rowconfigure(0, weight=1)
        self.chat_container.grid_columnconfigure(0, weight=1)

        self.chat_scrollable = ctk.CTkScrollableFrame(self.chat_container, fg_color="transparent")
        self.chat_scrollable.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # 3. Bottom Input Row
        bottom_row = ctk.CTkFrame(self.page_chatbot, fg_color="transparent")
        bottom_row.grid(row=2, column=0, sticky="ew", pady=(15, 0))

        self.chat_entry = ctk.CTkEntry(
            bottom_row,
            placeholder_text="Ask a question about the topology or request changes (e.g. 'add tag:database owned by group:shiner-tech')...",
            height=40,
            fg_color=("#ffffff", "#0f172a"),
            border_color=("#cbd5e1", "#334155")
        )
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.chat_entry.bind("<Return>", lambda e: self.send_chat_message())

        self.btn_send_chat = ctk.CTkButton(
            bottom_row,
            text="🚀 Send",
            width=100,
            height=40,
            fg_color=("#3b82f6", "#2563eb"),
            hover_color=("#2563eb", "#1d4ed8"),
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self.send_chat_message
        )
        self.btn_send_chat.pack(side="right")

        self.chat_history = []
        self.add_system_message("AI assistant initialized. Ask questions or request changes to your Tailscale network topology.")
        self.fetch_ollama_models()

    def add_system_message(self, text):
        lbl = ctk.CTkLabel(
            self.chat_scrollable,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=12, slant="italic"),
            text_color=("#64748b", "#94a3b8"),
            justify="center",
            pady=10
        )
        lbl.pack(fill="x", pady=4)
        self.scroll_chat_to_bottom()

    def add_user_message(self, text):
        frame = ctk.CTkFrame(self.chat_scrollable, fg_color="transparent")
        frame.pack(fill="x", pady=6)

        bubble = ctk.CTkFrame(frame, fg_color=("#3b82f6", "#2563eb"), corner_radius=12)
        bubble.pack(side="right", padx=10)

        lbl = ctk.CTkLabel(
            bubble,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="white",
            justify="left",
            wraplength=600,
            padx=12,
            pady=8
        )
        lbl.pack()
        self.scroll_chat_to_bottom()

    def add_assistant_message(self, text):
        frame = ctk.CTkFrame(self.chat_scrollable, fg_color="transparent")
        frame.pack(fill="x", pady=6)

        bubble = ctk.CTkFrame(
            frame,
            fg_color=("#f1f5f9", "#0f172a") if not text.startswith("Applying changes") else ("#ecfdf5", "#064e3b"),
            border_width=1,
            border_color=("#cbd5e1", "#1e293b"),
            corner_radius=12
        )
        bubble.pack(side="left", padx=10)

        lbl = ctk.CTkLabel(
            bubble,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=("#1e293b", "#cbd5e1") if not text.startswith("Applying changes") else ("#10b981", "#34d399"),
            justify="left",
            wraplength=600,
            padx=12,
            pady=8
        )
        lbl.pack()
        self.scroll_chat_to_bottom()

    def scroll_chat_to_bottom(self):
        self.chat_scrollable.update_idletasks()
        try:
            if hasattr(self.chat_scrollable, "_parent_canvas"):
                self.chat_scrollable._parent_canvas.yview_moveto(1.0)
            elif hasattr(self.chat_scrollable, "_canvas"):
                self.chat_scrollable._canvas.yview_moveto(1.0)
        except Exception:
            pass

    def fetch_ollama_models(self):
        def task():
            try:
                url = "http://100.106.252.1:11434/api/tags"
                req = urllib.request.urlopen(url, timeout=3)
                data = json.loads(req.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                if models:
                    self.after(0, lambda: self.combo_models.configure(values=models))
                    target = "qwen3.6:35b-a3b"
                    if target in models:
                        self.after(0, lambda: self.combo_models.set(target))
                    else:
                        self.after(0, lambda: self.combo_models.set(models[0]))
            except Exception:
                fallback = ["qwen3.6:35b-a3b", "qwen2.5-coder:7b", "deepseek-r1:70b", "gemma4:31b"]
                self.after(0, lambda: self.combo_models.configure(values=fallback))
                self.after(0, lambda: self.combo_models.set(fallback[0]))

        threading.Thread(target=task, daemon=True).start()

    def clear_chat(self):
        for widget in self.chat_scrollable.winfo_children():
            widget.destroy()
        self.chat_history = []
        self.add_system_message("Chat history cleared. Context is reset.")

    def send_chat_message(self):
        prompt = self.chat_entry.get().strip()
        if not prompt:
            return

        self.chat_entry.delete(0, "end")
        self.add_user_message(prompt)

        self.btn_send_chat.configure(state="disabled", text="⚡ Thinking...")
        self.chat_entry.configure(state="disabled")

        model = self.combo_models.get()
        threading.Thread(target=self.query_ollama, args=(prompt, model), daemon=True).start()

    def query_ollama(self, user_prompt, model_name):
        devices_list = []
        if hasattr(self, "topology_editor"):
            devices_list = self.topology_editor.get_devices_list()

        system_instruction = (
            "You are a helpful, expert AI Tailscale Network Administrator. "
            "Below is the current Tailscale Access Control List (ACL) JSON configuration, "
            "as well as a list of connected live devices on the network.\n\n"
            f"=== CURRENT ACL CONFIG ===\n{json.dumps(self.acl_data, indent=2)}\n\n"
            f"=== CONNECTED DEVICES ===\n{json.dumps(devices_list, indent=2)}\n\n"
            "INSTRUCTIONS:\n"
            "1. Answer the user's questions about the topology accurately based ONLY on the data above.\n"
            "2. If the user requests a change (e.g. adding a tag, user to a group, or creating a rule), "
            "explain what change you are planning to make, and then APPEND a JSON block containing "
            "the list of structured actions inside a ```json ... ``` code fence at the absolute end "
            "of your response. Do not perform any changes not requested.\n\n"
            "SUPPORTED ACTIONS SCHEMA:\n"
            "Your output block can contain a list of one or more actions in this format:\n"
            "```json\n"
            "[\n"
            "  {\n"
            "    \"action\": \"add_tag\",\n"
            "    \"tag\": \"tag:name\",\n"
            "    \"owners\": [\"group:admin\"]\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"delete_tag\",\n"
            "    \"tag\": \"tag:name\"\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"rename_tag\",\n"
            "    \"old\": \"tag:old\",\n"
            "    \"new\": \"tag:new\"\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"add_owner\",\n"
            "    \"tag\": \"tag:name\",\n"
            "    \"owner\": \"group:name\"\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"remove_owner\",\n"
            "    \"tag\": \"tag:name\",\n"
            "    \"owner\": \"group:name\"\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"add_group\",\n"
            "    \"group\": \"group:name\"\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"delete_group\",\n"
            "    \"group\": \"group:name\"\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"rename_group\",\n"
            "    \"old\": \"group:old\",\n"
            "    \"new\": \"group:new\"\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"add_user_to_group\",\n"
            "    \"group\": \"group:name\",\n"
            "    \"user\": \"user@email.com\"\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"remove_user_from_group\",\n"
            "    \"group\": \"group:name\",\n"
            "    \"user\": \"user@email.com\"\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"create_rule\",\n"
            "    \"src\": \"source\",\n"
            "    \"dst\": \"dest\",\n"
            "    \"ports\": \"*\"\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"edit_rule\",\n"
            "    \"index\": 0,\n"
            "    \"src\": \"source\",\n"
            "    \"dst\": \"dest\",\n"
            "    \"ports\": \"*\"\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"delete_rule\",\n"
            "    \"index\": 0\n"
            "  },\n"
            "  {\n"
            "    \"action\": \"tag_device\",\n"
            "    \"device\": \"hostname\",\n"
            "    \"tag\": \"tag:name\"\n"
            "  }\n"
            "]\n"
            "```\n"
            "Make sure your explanation is concise and structured."
        )

        messages = [
            {"role": "system", "content": system_instruction}
        ]

        for role, text in self.chat_history:
            messages.append({"role": role, "content": text})

        messages.append({"role": "user", "content": user_prompt})
        self.chat_history.append(("user", user_prompt))

        try:
            url = "http://100.106.252.1:11434/api/chat"
            payload = json.dumps({
                "model": model_name,
                "messages": messages,
                "stream": False
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"}
            )

            response = urllib.request.urlopen(req, timeout=120)
            res_data = json.loads(response.read().decode())

            ai_content = res_data.get("message", {}).get("content", "").strip()
            self.chat_history.append(("assistant", ai_content))

            self.after(0, lambda: self.handle_ai_response(ai_content))
        except Exception as e:
            err_msg = f"Network communication failed with Ollama at 100.106.252.1:\n{e}"
            self.after(0, lambda: self.handle_query_error(err_msg))

    def handle_ai_response(self, text):
        self.btn_send_chat.configure(state="normal", text="🚀 Send")
        self.chat_entry.configure(state="normal")

        json_actions = []
        cleaned_text = text

        start_marker = "```json"
        end_marker = "```"

        if start_marker in text:
            try:
                parts = text.split(start_marker, 1)
                pre_text = parts[0]
                remainder = parts[1]
                if end_marker in remainder:
                    json_str, post_text = remainder.split(end_marker, 1)
                    json_actions = json.loads(json_str.strip())
                    cleaned_text = (pre_text + "\n" + post_text).strip()
            except Exception as e:
                cleaned_text += f"\n\n[Warning: Found JSON action block, but failed to parse: {e}]"

        self.add_assistant_message(cleaned_text)

        if json_actions:
            self.process_ai_actions(json_actions)

    def process_ai_actions(self, actions):
        desc = "The AI Assistant proposes the following updates:\n\n"
        for act in actions:
            a_type = act.get("action")
            if a_type == "add_tag":
                desc += f"• Create Network Tag: {act.get('tag')} (owners: {act.get('owners')})\n"
            elif a_type == "delete_tag":
                desc += f"• Delete Network Tag: {act.get('tag')}\n"
            elif a_type == "rename_tag":
                desc += f"• Rename Tag: {act.get('old')} ➔ {act.get('new')}\n"
            elif a_type == "add_owner":
                desc += f"• Add Owner '{act.get('owner')}' to Tag '{act.get('tag')}'\n"
            elif a_type == "remove_owner":
                desc += f"• Remove Owner '{act.get('owner')}' from Tag '{act.get('tag')}'\n"
            elif a_type == "add_group":
                desc += f"• Create User Group: {act.get('group')}\n"
            elif a_type == "delete_group":
                desc += f"• Delete User Group: {act.get('group')}\n"
            elif a_type == "rename_group":
                desc += f"• Rename Group: {act.get('old')} ➔ {act.get('new')}\n"
            elif a_type == "add_user_to_group":
                desc += f"• Add User '{act.get('user')}' to Group '{act.get('group')}'\n"
            elif a_type == "remove_user_from_group":
                desc += f"• Remove User '{act.get('user')}' from Group '{act.get('group')}'\n"
            elif a_type == "create_rule":
                desc += f"• Create Rule: {act.get('src')} ➔ {act.get('dst')}:{act.get('ports', '*')}\n"
            elif a_type == "edit_rule":
                desc += f"• Edit Rule #{act.get('index')}: Set Src: {act.get('src')}, Dst: {act.get('dst')}:{act.get('ports', '*')}\n"
            elif a_type == "delete_rule":
                desc += f"• Delete Access Rule #{act.get('index')}\n"
            elif a_type == "tag_device":
                desc += f"• Tag Device '{act.get('device')}' with Tag '{act.get('tag')}'\n"
            else:
                desc += f"• Unknown Action: {a_type}\n"

        desc += "\nDo you want to apply these configuration updates to the network?"

        if messagebox.askyesno("Verify Proposed Config Updates", desc):
            try:
                for act in actions:
                    a_type = act.get("action")
                    if a_type == "add_tag":
                        tag = act.get("tag")
                        owners = act.get("owners", ["autogroup:admin"])
                        self.acl_data.setdefault("tagOwners", {})[tag] = owners
                    elif a_type == "delete_tag":
                        tag = act.get("tag")
                        self.acl_data.get("tagOwners", {}).pop(tag, None)
                        self.acl_data["acls"] = [r for r in self.acl_data.get("acls", []) if tag not in r.get("src", [])]
                        for r in self.acl_data.get("acls", []):
                            r["dst"] = [d for d in r.get("dst", []) if not d.startswith(f"{tag}:")]
                    elif a_type == "rename_tag":
                        old = act.get("old")
                        new = act.get("new")
                        if old in self.acl_data.get("tagOwners", {}):
                            owners = self.acl_data["tagOwners"].pop(old)
                            self.acl_data["tagOwners"][new] = owners
                            for r in self.acl_data.get("acls", []):
                                if old in r.get("src", []):
                                    r["src"] = [new if s == old else s for s in r["src"]]
                                r["dst"] = [d.replace(f"{old}:", f"{new}:", 1) if d.startswith(f"{old}:") else d for d in r.get("dst", [])]
                    elif a_type == "add_owner":
                        tag = act.get("tag")
                        o = act.get("owner")
                        self.acl_data.setdefault("tagOwners", {}).setdefault(tag, []).append(o)
                    elif a_type == "remove_owner":
                        tag = act.get("tag")
                        o = act.get("owner")
                        if o in self.acl_data.get("tagOwners", {}).get(tag, []):
                            self.acl_data["tagOwners"][tag].remove(o)
                    elif a_type == "add_group":
                        g = act.get("group")
                        self.acl_data.setdefault("groups", {})[g] = []
                    elif a_type == "delete_group":
                        g = act.get("group")
                        self.acl_data.get("groups", {}).pop(g, None)
                    elif a_type == "rename_group":
                        old = act.get("old")
                        new = act.get("new")
                        if old in self.acl_data.get("groups", {}):
                            users = self.acl_data["groups"].pop(old)
                            self.acl_data["groups"][new] = users
                    elif a_type == "add_user_to_group":
                        g = act.get("group")
                        u = act.get("user")
                        self.acl_data.setdefault("groups", {}).setdefault(g, [])
                        if u not in self.acl_data["groups"][g]:
                            self.acl_data["groups"][g].append(u)
                    elif a_type == "remove_user_from_group":
                        g = act.get("group")
                        u = act.get("user")
                        if u in self.acl_data.get("groups", {}).get(g, []):
                            self.acl_data["groups"][g].remove(u)
                    elif a_type == "create_rule":
                        src = act.get("src")
                        dst = act.get("dst")
                        ports = act.get("ports", "*")
                        self.acl_data.setdefault("acls", []).append({
                            "action": "accept",
                            "src": [src],
                            "dst": [f"{dst}:{ports}"]
                        })
                    elif a_type == "edit_rule":
                        idx = act.get("index")
                        if idx < len(self.acl_data.get("acls", [])):
                            r = self.acl_data["acls"][idx]
                            r["src"] = [act.get("src")]
                            r["dst"] = [f"{act.get('dst')}:{act.get('ports', '*')}"]
                    elif a_type == "delete_rule":
                        idx = act.get("index")
                        if idx < len(self.acl_data.get("acls", [])):
                            del self.acl_data["acls"][idx]
                    elif a_type == "tag_device":
                        device_host = act.get("device")
                        tag = act.get("tag")
                        self.update_device_tag_in_file(device_host, tag)

                self.refresh_ui()
                self.add_assistant_message("Applying changes... Done! Network configuration updated successfully.")
            except Exception as ex:
                messagebox.showerror("Error Applying Actions", f"An error occurred while executing changes: {ex}")

    def update_device_tag_in_file(self, hostname, tag_name, new_owner=None):
        md_path = "Tailscale Devices.md"
        if not os.path.exists(md_path):
            return False
        try:
            # Clean hostname to prevent mismatches (e.g. from (Self) suffix or spaces)
            clean_hostname = hostname.split()[0] if hostname else ""
            with open(md_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = []
            header_index = -1
            separator_index = -1
            updated = False

            for idx, line in enumerate(lines):
                if "IP Address" in line and "Hostname" in line:
                    header_index = idx
                elif "---" in line and header_index != -1 and separator_index == -1:
                    separator_index = idx

            if header_index == -1:
                return False

            header_line = lines[header_index].strip()
            has_tags_col = "Tags" in header_line

            if not has_tags_col:
                lines[header_index] = header_line.rstrip(" |") + " | Tags |\n"
                lines[separator_index] = lines[separator_index].strip().rstrip(" |") + "---| \n"

            for idx, line in enumerate(lines):
                if idx <= separator_index or not line.strip().startswith("|"):
                    new_lines.append(line)
                    continue

                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5:
                    row_host = parts[2].split()[0]
                    if row_host == clean_hostname:
                        updated = True
                        # Set owner
                        if new_owner:
                            parts[3] = new_owner
                        elif tag_name.strip() == "-":
                            parts[3] = "reid.sutton@shinertechnologies.com"
                        else:
                            parts[3] = "tagged-devices"

                        # Ensure enough space for Tags column
                        while len(parts) < 8:
                            parts.append("")
                        parts[6] = f" {tag_name} "
                        parts[7] = " \n"

                        new_line = "|".join(parts)
                        new_lines.append(new_line)
                    else:
                        if not has_tags_col:
                            while len(parts) < 8:
                                parts.append("")
                            if parts[6].strip() == "":
                                parts[6] = " - "
                            parts[7] = " \n"
                            new_line = "|".join(parts)
                            new_lines.append(new_line)
                        else:
                            new_lines.append(line)
                else:
                    new_lines.append(line)

            if not updated:
                return False

            with open(md_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return True
        except Exception as e:
            print(f"Error updating device tag: {e}")
            return False

    def rename_tag_in_devices_file(self, old_tag, new_tag):
        md_path = "Tailscale Devices.md"
        if not os.path.exists(md_path):
            return False
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = []
            header_index = -1
            separator_index = -1

            for idx, line in enumerate(lines):
                if "IP Address" in line and "Hostname" in line:
                    header_index = idx
                elif "---" in line and header_index != -1 and separator_index == -1:
                    separator_index = idx

            if header_index == -1:
                return False

            header_line = lines[header_index].strip()
            has_tags_col = "Tags" in header_line
            if not has_tags_col:
                return True

            for idx, line in enumerate(lines):
                if idx <= separator_index or not line.strip().startswith("|"):
                    new_lines.append(line)
                    continue

                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 7:
                    tags_str = parts[6].strip()
                    if tags_str and tags_str != "-":
                        t_list = [t.strip() for t in tags_str.split(",") if t.strip()]
                        updated_tags = []
                        changed = False
                        for t in t_list:
                            t_full = t if t.startswith("tag:") else f"tag:{t}"
                            old_full = old_tag if old_tag.startswith("tag:") else f"tag:{old_tag}"
                            new_full = new_tag if new_tag.startswith("tag:") else f"tag:{new_tag}"
                            if t_full == old_full:
                                updated_tags.append(new_full)
                                changed = True
                            else:
                                updated_tags.append(t)
                        
                        if changed:
                            parts[6] = f" {', '.join(updated_tags)} "
                            new_line = "|".join(parts)
                            if not new_line.endswith("\n"):
                                new_line += "\n"
                            new_lines.append(new_line)
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            with open(md_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return True
        except Exception as e:
            print(f"Error renaming tag in devices: {e}")
            return False

    def delete_tag_from_devices_file(self, tag_name):
        md_path = "Tailscale Devices.md"
        if not os.path.exists(md_path):
            return False
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = []
            header_index = -1
            separator_index = -1

            for idx, line in enumerate(lines):
                if "IP Address" in line and "Hostname" in line:
                    header_index = idx
                elif "---" in line and header_index != -1 and separator_index == -1:
                    separator_index = idx

            if header_index == -1:
                return False

            header_line = lines[header_index].strip()
            has_tags_col = "Tags" in header_line
            if not has_tags_col:
                return True

            for idx, line in enumerate(lines):
                if idx <= separator_index or not line.strip().startswith("|"):
                    new_lines.append(line)
                    continue

                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 7:
                    tags_str = parts[6].strip()
                    if tags_str and tags_str != "-":
                        t_list = [t.strip() for t in tags_str.split(",") if t.strip()]
                        updated_tags = []
                        changed = False
                        for t in t_list:
                            t_full = t if t.startswith("tag:") else f"tag:{t}"
                            del_full = tag_name if tag_name.startswith("tag:") else f"tag:{tag_name}"
                            if t_full == del_full:
                                changed = True
                            else:
                                updated_tags.append(t)
                        
                        if changed:
                            if not updated_tags:
                                parts[6] = " - "
                            else:
                                parts[6] = f" {', '.join(updated_tags)} "
                            new_line = "|".join(parts)
                            if not new_line.endswith("\n"):
                                new_line += "\n"
                            new_lines.append(new_line)
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            with open(md_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return True
        except Exception as e:
            print(f"Error deleting tag from devices: {e}")
            return False

    def handle_query_error(self, err_msg):
        self.btn_send_chat.configure(state="normal", text="🚀 Send")
        self.chat_entry.configure(state="normal")
        self.add_assistant_message(err_msg)


if __name__ == "__main__":
    app = ACLManagerV5()
    app.mainloop()
