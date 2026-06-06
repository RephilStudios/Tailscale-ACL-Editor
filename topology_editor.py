import json
import os
import tkinter as tk
import tkinter.messagebox as messagebox
import tkinter.simpledialog as simpledialog

import customtkinter as ctk
import json5


class ConnectionLinkDialog(ctk.CTkToplevel):
    def __init__(self, parent, src_name, dst_name):
        super().__init__(parent)
        self.title("Define Connection Type")
        self.geometry("460x180")
        self.resizable(False, False)

        # Center the dialog on the parent window
        self.transient(parent)
        self.grab_set()

        self.choice = None  # Will be 'acl', 'owner', or None

        # CustomTkinter styling - Match dark slate theme
        self.configure(fg_color="#1e293b")

        # Label
        lbl = ctk.CTkLabel(
            self,
            text=f"Choose the type of link to create:\n\n{src_name} → {dst_name}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#f8fafc",
            justify="center",
        )
        lbl.pack(pady=(20, 15), padx=20)

        # Buttons frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)

        # Access Rule Button (Green)
        btn_acl = ctk.CTkButton(
            btn_frame,
            text="Access Rule",
            fg_color="#10b981",
            hover_color="#059669",
            text_color="#ffffff",
            font=ctk.CTkFont(weight="bold"),
            command=self.on_acl,
        )
        btn_acl.pack(side="left", expand=True, padx=5)

        # Tag Owner Button (Amber)
        btn_owner = ctk.CTkButton(
            btn_frame,
            text="Tag Owner",
            fg_color="#f59e0b",
            hover_color="#d97706",
            text_color="#ffffff",
            font=ctk.CTkFont(weight="bold"),
            command=self.on_owner,
        )
        btn_owner.pack(side="left", expand=True, padx=5)

        # Cancel Button
        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            fg_color="#475569",
            hover_color="#334155",
            text_color="#ffffff",
            command=self.destroy,
        )
        btn_cancel.pack(side="left", expand=True, padx=5)

        # Center window relative to parent
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

        # Wait for dialog to be closed
        self.wait_window()

    def on_acl(self):
        self.choice = "acl"
        self.destroy()

    def on_owner(self):
        self.choice = "owner"
        self.destroy()


class Node:
    def __init__(self, node_id, name, node_type, x=0, y=0, details=None):
        self.id = node_id
        self.name = name
        self.type = node_type  # 'user', 'group', 'tag', 'autogroup', 'device'
        self.x = x
        self.y = y
        self.width = 180
        self.height = 90
        self.details = details or {}


class Edge:
    def __init__(self, edge_id, src_id, dst_id, edge_type, ports=None, rule_index=None):
        self.id = edge_id
        self.src_id = src_id
        self.dst_id = dst_id
        self.type = edge_type  # 'acl', 'membership', 'ownership', 'device'
        self.ports = ports
        self.rule_index = rule_index


class TopologyEditor(ctk.CTkFrame):
    def __init__(self, parent, acl_data, refresh_callback=None):
        super().__init__(parent)
        self.acl_data = acl_data
        self.refresh_callback = refresh_callback
        self.loaded_filepath = None

        self.nodes = {}
        self.edges = []
        self.selected_node_id = None
        self.selected_edge_id = None
        self.zoom_factor = 1.0
        self.last_hovered_pin = None
        self.added_users = set()
        self.coordinate_cache = {}

        # Custom column ordering (saved alongside positions)
        self.custom_column_orders = {}  # {col_key: [nid, nid, ...]}

        # Highlight/Dimming state
        self.connected_nodes_set = set()
        self.connected_edges_set = set()
        self.animating_dim = False
        self.visual_dim_levels = {}

        # Dragging state
        self.drag_node_id = None
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.node_initial_x = 0
        self.node_initial_y = 0

        # Connection drawing state
        self.conn_start_node_id = None
        self.conn_start_x = 0
        self.conn_start_y = 0
        self.temp_conn_line = None

        # Visibility layers
        self.show_acl_rules = tk.BooleanVar(value=True)
        self.show_group_members = tk.BooleanVar(value=True)
        self.show_tag_owners = tk.BooleanVar(value=False)
        self.show_devices = tk.BooleanVar(value=True)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.setup_ui()

    def setup_ui(self):
        # 1. Left Sidebar - Controls
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 2))

        ctk.CTkLabel(
            self.sidebar,
            text="Topology Controls",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(15, 10), padx=10)

        # Node Creation Buttons
        btn_f = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_f.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(
            btn_f, text="+ Add Tag", command=self.add_tag_node, height=28
        ).pack(pady=4, fill="x")
        ctk.CTkButton(
            btn_f, text="+ Add Group", command=self.add_group_node, height=28
        ).pack(pady=4, fill="x")
        ctk.CTkButton(
            btn_f, text="+ Add User", command=self.add_user_node, height=28
        ).pack(pady=4, fill="x")

        ctk.CTkLabel(
            self.sidebar, text="Visibility Layers", font=ctk.CTkFont(weight="bold")
        ).pack(pady=(15, 5), padx=10)

        ctk.CTkCheckBox(
            self.sidebar,
            text="ACL Rules (Green)",
            variable=self.show_acl_rules,
            command=self.on_vis_layer_changed,
        ).pack(anchor="w", padx=15, pady=4)
        ctk.CTkCheckBox(
            self.sidebar,
            text="Group Members (Purple)",
            variable=self.show_group_members,
            command=self.on_vis_layer_changed,
        ).pack(anchor="w", padx=15, pady=4)
        ctk.CTkCheckBox(
            self.sidebar,
            text="Tag Owners (Amber)",
            variable=self.show_tag_owners,
            command=self.on_vis_layer_changed,
        ).pack(anchor="w", padx=15, pady=4)
        ctk.CTkCheckBox(
            self.sidebar,
            text="Live Devices (Slate)",
            variable=self.show_devices,
            command=self.on_vis_layer_changed,
        ).pack(anchor="w", padx=15, pady=4)

        ctk.CTkLabel(
            self.sidebar, text="Layout Actions", font=ctk.CTkFont(weight="bold")
        ).pack(pady=(20, 5), padx=10)
        ctk.CTkButton(
            self.sidebar,
            text="Auto-Layout Columns",
            fg_color="#3b82f6",
            hover_color="#2563eb",
            command=self.apply_auto_layout,
        ).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(
            self.sidebar,
            text="Save Node Layout",
            fg_color="#10b981",
            hover_color="#059669",
            command=self.save_positions,
        ).pack(pady=5, padx=10, fill="x")

        # Zoom Actions
        ctk.CTkLabel(self.sidebar, text="Zoom", font=ctk.CTkFont(weight="bold")).pack(
            pady=(15, 5), padx=10
        )
        zoom_f = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        zoom_f.pack(fill="x", padx=10, pady=2)

        self.btn_zoom_out = ctk.CTkButton(
            zoom_f, text="-", width=40, height=28, command=self.zoom_out
        )
        self.btn_zoom_out.pack(side="left", padx=5)

        self.lbl_zoom = ctk.CTkLabel(
            zoom_f, text="100%", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_zoom.pack(side="left", fill="x", expand=True)

        self.btn_zoom_in = ctk.CTkButton(
            zoom_f, text="+", width=40, height=28, command=self.zoom_in
        )
        self.btn_zoom_in.pack(side="right", padx=5)

        self.lbl_help = ctk.CTkLabel(
            self.sidebar,
            text="* Left-click to select / drag nodes.\n* Right-click + drag to pan.\n* Drag from green node circles\n  to create ACL rules.\n* Arrow keys reorder selected node\n  within its auto-layout column.",
            font=ctk.CTkFont(size=10),
            justify="left",
            text_color="#94a3b8",
        )
        self.lbl_help.pack(pady=20, padx=10, side="bottom")

        # 2. Central Area - Canvas with Scrollbars
        self.canvas_container = ctk.CTkFrame(self)
        self.canvas_container.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        self.canvas_container.grid_rowconfigure(0, weight=1)
        self.canvas_container.grid_columnconfigure(0, weight=1)

        # Custom dark palette background matching VS Code/Tailwind slate-950
        self.canvas = tk.Canvas(
            self.canvas_container,
            bg="#0f172a",
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Scrollbars
        self.vsb = ctk.CTkScrollbar(
            self.canvas_container, orientation="vertical", command=self.canvas.yview
        )
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb = ctk.CTkScrollbar(
            self.canvas_container, orientation="horizontal", command=self.canvas.xview
        )
        self.hsb.grid(row=1, column=0, sticky="ew")

        self.canvas.configure(xscrollcommand=self.hsb.set, yscrollcommand=self.vsb.set)
        self.canvas.configure(scrollregion=(0, 0, 4000, 4000))

        # Canvas Binds
        self.canvas.bind("<Button-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        # Panning binds
        self.canvas.bind("<Button-3>", self.on_pan_press)
        self.canvas.bind("<B3-Motion>", self.on_pan_drag)

        self.canvas.bind("<Motion>", self.on_mouse_motion)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)

        # Arrow key column reordering (on both canvas and frame for focus robustness)
        self.canvas.bind("<KeyPress-Up>", self._on_key_column_up)
        self.canvas.bind("<KeyPress-Down>", self._on_key_column_down)
        self.bind("<KeyPress-Up>", self._on_key_column_up)
        self.bind("<KeyPress-Down>", self._on_key_column_down)

        # 3. Right Sidebar - Inspector Panel
        self.inspector = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.inspector.grid(row=0, column=2, sticky="nsew", padx=(2, 0))

        self.setup_inspector_empty()

    # ---- INSPECTOR PANEL MODES ----
    def setup_inspector_empty(self):
        for widget in self.inspector.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.inspector, text="Inspector", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(15, 10), padx=10)

        ctk.CTkLabel(
            self.inspector,
            text="Select a node or connection line\nto view and edit properties.",
            font=ctk.CTkFont(size=12),
            text_color="#64748b",
            wraplength=200,
        ).pack(pady=40, padx=10)

    def show_node_inspector(self, node_id):
        for widget in self.inspector.winfo_children():
            widget.destroy()

        node = self.nodes.get(node_id)
        if not node:
            self.setup_inspector_empty()
            return

        ctk.CTkLabel(
            self.inspector,
            text="Node Inspector",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(15, 5), padx=10)

        # Node Header
        lbl_type = ctk.CTkLabel(
            self.inspector,
            text=node.type.upper(),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#38bdf8",
        )
        lbl_type.pack()

        lbl_name = ctk.CTkLabel(
            self.inspector,
            text=node.name,
            font=ctk.CTkFont(size=14, weight="bold"),
            wraplength=220,
        )
        lbl_name.pack(pady=5, padx=10)

        ctk.CTkFrame(self.inspector, height=2, fg_color="#334155").pack(
            fill="x", padx=10, pady=10
        )

        # Edit Section based on Type
        if node.type == "group":
            self.show_group_editor(node)
        elif node.type == "tag":
            self.show_tag_editor(node)
        elif node.type == "user":
            self.show_user_editor(node)
        elif node.type == "device":
            self.show_device_info(node)
        elif node.type == "autogroup":
            ctk.CTkLabel(
                self.inspector,
                text="Autogroups are built-in Tailscale groups and cannot be modified directly.",
                font=ctk.CTkFont(size=11),
                text_color="#94a3b8",
                wraplength=200,
            ).pack(pady=10, padx=10)

        # Delete Node (Non-autogroups and non-devices)
        if node.type not in ["autogroup", "device"]:
            ctk.CTkFrame(self.inspector, height=2, fg_color="#334155").pack(
                fill="x", padx=10, pady=10
            )
            ctk.CTkButton(
                self.inspector,
                text="Delete Node",
                fg_color="#ef4444",
                hover_color="#dc2626",
                command=lambda: self.delete_node_action(node_id),
            ).pack(pady=10, padx=20, fill="x")

    def show_group_editor(self, node):
        members = node.details.get("members", [])
        ctk.CTkLabel(
            self.inspector,
            text=f"Members ({len(members)}):",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=15, pady=(5, 0))

        # Scrollable user list
        scroll = ctk.CTkScrollableFrame(self.inspector, height=150)
        scroll.pack(fill="x", padx=15, pady=5)

        for u in members:
            f = ctk.CTkFrame(scroll, fg_color="transparent")
            f.pack(fill="x", pady=2)
            # Pack delete button FIRST (right-anchored) so its width is reserved
            # before the label fills the remaining space — prevents email overflow.
            btn_del = ctk.CTkButton(
                f,
                text="×",
                width=24,
                height=22,
                fg_color="#ef4444",
                hover_color="#dc2626",
                command=lambda usr=u: self.remove_user_from_group_action(node.id, usr),
            )
            btn_del.pack(side="right", padx=(4, 0))
            ctk.CTkLabel(
                f, text=u, font=ctk.CTkFont(size=11), anchor="w", wraplength=155
            ).pack(side="left", fill="x", expand=True)

        # Add member input
        add_f = ctk.CTkFrame(self.inspector, fg_color="transparent")
        add_f.pack(fill="x", padx=15, pady=10)

        self.entry_new_member = ctk.CTkEntry(
            add_f, placeholder_text="user@email.com", height=28
        )
        self.entry_new_member.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_add = ctk.CTkButton(
            add_f,
            text="+",
            width=30,
            height=28,
            command=lambda: self.add_user_to_group_action(node.id),
        )
        btn_add.pack(side="right")

    def show_tag_editor(self, node):
        owners = node.details.get("owners", [])
        ctk.CTkLabel(
            self.inspector,
            text=f"Owners ({len(owners)}):",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=15, pady=(5, 0))

        # Scrollable owners list
        scroll = ctk.CTkScrollableFrame(self.inspector, height=120)
        scroll.pack(fill="x", padx=15, pady=5)

        for o in owners:
            f = ctk.CTkFrame(scroll, fg_color="transparent")
            f.pack(fill="x", pady=2)

            disp_name = o.replace("group:", "")
            ctk.CTkLabel(f, text=disp_name, font=ctk.CTkFont(size=11), anchor="w").pack(
                side="left", fill="x", expand=True
            )
            btn_del = ctk.CTkButton(
                f,
                text="×",
                width=20,
                height=20,
                fg_color="#ef4444",
                hover_color="#dc2626",
                command=lambda owner=o: self.remove_owner_from_tag_action(
                    node.id, owner
                ),
            )
            btn_del.pack(side="right")

        # Add Owner combobox
        all_options = self.get_all_possible_owners()
        available_options = [opt for opt in all_options if opt not in owners]

        add_f = ctk.CTkFrame(self.inspector, fg_color="transparent")
        add_f.pack(fill="x", padx=15, pady=10)

        if available_options:
            self.combo_new_owner = ctk.CTkComboBox(
                add_f, values=available_options, height=28
            )
            self.combo_new_owner.set(available_options[0])
            self.combo_new_owner.pack(side="left", fill="x", expand=True, padx=(0, 5))

            btn_add = ctk.CTkButton(
                add_f,
                text="+",
                width=30,
                height=28,
                command=lambda: self.add_owner_to_tag_action(node.id),
            )
            btn_add.pack(side="right")
        else:
            ctk.CTkLabel(
                self.inspector,
                text="All groups/users are owners.",
                font=ctk.CTkFont(size=10),
                text_color="#64748b",
            ).pack()

    def show_user_editor(self, node):
        # Show what groups this user belongs to
        user_groups = []
        for g, users in self.acl_data.get("groups", {}).items():
            if node.id in users:
                user_groups.append(g)

        ctk.CTkLabel(
            self.inspector, text="Group Memberships:", font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=15, pady=(5, 0))

        if user_groups:
            for g in user_groups:
                ctk.CTkLabel(
                    self.inspector, text=f"• {g}", font=ctk.CTkFont(size=12), anchor="w"
                ).pack(anchor="w", padx=25, pady=2)
        else:
            ctk.CTkLabel(
                self.inspector,
                text="Not in any groups.",
                font=ctk.CTkFont(size=12, slant="italic"),
                text_color="#64748b",
            ).pack(anchor="w", padx=25, pady=2)

    def show_device_info(self, node):
        ips = node.details.get("ips", [])
        os_name = node.details.get("os", "Unknown")
        status = node.details.get("status", "Offline")
        owner = node.details.get("owner", "None")
        tags = node.details.get("tags", [])

        # Display details in vertical grid
        f_details = ctk.CTkFrame(self.inspector, fg_color="transparent")
        f_details.pack(fill="x", padx=15, pady=5)

        labels = [
            ("IP Address:", ips[0] if ips else "Unknown"),
            ("OS:", os_name),
            ("Status:", status.capitalize()),
            ("Owner:", owner.replace("@", "@\n")),
        ]

        for i, (k, v) in enumerate(labels):
            lbl_k = ctk.CTkLabel(
                f_details, text=k, font=ctk.CTkFont(weight="bold", size=11), anchor="w"
            )
            lbl_k.grid(row=i, column=0, sticky="nw", pady=4)

            lbl_v = ctk.CTkLabel(
                f_details, text=v, font=ctk.CTkFont(size=11), anchor="w", justify="left"
            )
            lbl_v.grid(row=i, column=1, sticky="nw", padx=10, pady=4)

        ctk.CTkLabel(
            self.inspector,
            text="Assigned Tags:",
            font=ctk.CTkFont(weight="bold", size=11),
        ).pack(anchor="w", padx=15, pady=(10, 0))
        if tags:
            for t in tags:
                ctk.CTkLabel(
                    self.inspector, text=f"• {t}", font=ctk.CTkFont(size=11), anchor="w"
                ).pack(anchor="w", padx=25, pady=2)
        else:
            ctk.CTkLabel(
                self.inspector,
                text="None (untagged)",
                font=ctk.CTkFont(size=11, slant="italic"),
                anchor="w",
            ).pack(anchor="w", padx=25, pady=2)

        ctk.CTkFrame(self.inspector, height=2, fg_color="#334155").pack(
            fill="x", padx=10, pady=10
        )
        ctk.CTkButton(
            self.inspector,
            text="🔑 Manage Tag Owners",
            fg_color="#3b82f6",
            hover_color="#2563eb",
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self.trigger_manage_device_tag_owners(node.name),
        ).pack(pady=10, padx=20, fill="x")

    def trigger_manage_device_tag_owners(self, device_name):
        app = self.winfo_toplevel()
        if hasattr(app, "manage_device_tag_owners"):
            app.manage_device_tag_owners(device_name)
            if self.refresh_callback:
                self.refresh_callback()
            self.load_data(self.acl_data, self.loaded_filepath)
            self.show_node_inspector(device_name)

    def show_edge_inspector(self, edge_id):
        for widget in self.inspector.winfo_children():
            widget.destroy()

        # Find edge
        edge = None
        for e in self.edges:
            if e.id == edge_id:
                edge = e
                break

        if not edge or edge.type != "acl":
            self.setup_inspector_empty()
            return

        ctk.CTkLabel(
            self.inspector,
            text="Rule Inspector",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(15, 5), padx=10)

        ctk.CTkLabel(
            self.inspector,
            text="ACCESS RULE",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#10b981",
        ).pack()

        # Connections display
        f_conn = ctk.CTkFrame(
            self.inspector, fg_color="#1e293b", border_color="#334155", border_width=1
        )
        f_conn.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            f_conn,
            text=edge.src_id,
            font=ctk.CTkFont(weight="bold", size=11),
            wraplength=200,
        ).pack(pady=4)
        ctk.CTkLabel(
            f_conn,
            text="⬇ ACCESS ALLOWED TO ⬇",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#94a3b8",
        ).pack()
        ctk.CTkLabel(
            f_conn,
            text=edge.dst_id,
            font=ctk.CTkFont(weight="bold", size=11),
            wraplength=200,
        ).pack(pady=4)

        ctk.CTkFrame(self.inspector, height=2, fg_color="#334155").pack(
            fill="x", padx=10, pady=10
        )

        # Port configuration
        ctk.CTkLabel(
            self.inspector, text="Allowed Ports:", font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=15, pady=5)

        self.entry_ports = ctk.CTkEntry(
            self.inspector, placeholder_text="e.g. *, 22, 80,443"
        )
        self.entry_ports.insert(0, edge.ports or "*")
        self.entry_ports.pack(fill="x", padx=15, pady=5)

        ctk.CTkButton(
            self.inspector,
            text="Apply Port Config",
            command=lambda: self.update_ports_action(edge),
        ).pack(pady=5, padx=20, fill="x")

        ctk.CTkFrame(self.inspector, height=2, fg_color="#334155").pack(
            fill="x", padx=10, pady=10
        )

        # Delete Rule Button
        ctk.CTkButton(
            self.inspector,
            text="Delete Access Rule",
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=lambda: self.delete_rule_action(edge.rule_index),
        ).pack(pady=10, padx=20, fill="x")

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
                            del_full = (
                                tag_name
                                if tag_name.startswith("tag:")
                                else f"tag:{tag_name}"
                            )
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

    # ---- ACTIONS CORE ----
    def delete_node_action(self, node_id):
        node = self.nodes.get(node_id)
        if not node:
            return

        if not messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete {node.name} and all its rules?",
        ):
            return

        if node.type == "group":
            # Remove from groups list
            self.acl_data.setdefault("groups", {}).pop(node_id, None)
            # Remove from tagOwners
            for t, owners in self.acl_data.get("tagOwners", {}).items():
                if node_id in owners:
                    owners.remove(node_id)
            # Remove from ACL src rules
            self.acl_data["acls"] = [
                r
                for r in self.acl_data.get("acls", [])
                if node_id not in r.get("src", [])
            ]

        elif node.type == "tag":
            # Remove from tagOwners list
            self.acl_data.setdefault("tagOwners", {}).pop(node_id, None)
            # Remove associated ACL rules
            new_acls = []
            for r in self.acl_data.get("acls", []):
                if node_id in r.get("src", []):
                    continue
                # Remove destinations that match tag:name:* or tag:name:port
                new_dst = [
                    d for d in r.get("dst", []) if not d.startswith(f"{node_id}:")
                ]
                if new_dst:
                    r["dst"] = new_dst
                    new_acls.append(r)
            self.acl_data["acls"] = new_acls
            self.delete_tag_from_devices_file(node_id)

        elif node.type == "user":
            # Remove from all groups
            for g, users in self.acl_data.get("groups", {}).items():
                if node_id in users:
                    users.remove(node_id)
            # Remove from ACL src rules
            self.acl_data["acls"] = [
                r
                for r in self.acl_data.get("acls", [])
                if node_id not in r.get("src", [])
            ]
            self.added_users.discard(node_id)

        self.selected_node_id = None
        self.setup_inspector_empty()
        self.trigger_refresh()

    def remove_user_from_group_action(self, group_id, user):
        if group_id in self.acl_data.get("groups", {}):
            try:
                self.acl_data["groups"][group_id].remove(user)
                self.trigger_refresh()
                self.show_node_inspector(group_id)
            except ValueError:
                pass

    def add_user_to_group_action(self, group_id):
        val = self.entry_new_member.get().strip()
        if val:
            if group_id in self.acl_data.get("groups", {}):
                if val not in self.acl_data["groups"][group_id]:
                    self.acl_data["groups"][group_id].append(val)
                    self.trigger_refresh()
                    self.show_node_inspector(group_id)

    def remove_owner_from_tag_action(self, tag_id, owner):
        if tag_id in self.acl_data.get("tagOwners", {}):
            try:
                self.acl_data["tagOwners"][tag_id].remove(owner)
                self.trigger_refresh()
                self.show_node_inspector(tag_id)
            except ValueError:
                pass

    def add_owner_to_tag_action(self, tag_id):
        val = self.combo_new_owner.get()
        if val:
            if tag_id in self.acl_data.get("tagOwners", {}):
                if val not in self.acl_data["tagOwners"][tag_id]:
                    self.acl_data["tagOwners"][tag_id].append(val)
                    self.trigger_refresh()
                    self.show_node_inspector(tag_id)

    def update_ports_action(self, edge):
        new_ports = self.entry_ports.get().strip()
        if not new_ports:
            new_ports = "*"

        try:
            rule = self.acl_data["acls"][edge.rule_index]
            # Replace target:port
            dst = rule["dst"][0]
            target = dst.rsplit(":", 1)[0]
            rule["dst"] = [f"{target}:{new_ports}"]

            self.trigger_refresh()
            self.show_edge_inspector(edge.id)
            messagebox.showinfo("Success", "Rule port updated successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not update port: {e}")

    def delete_rule_action(self, index):
        if messagebox.askyesno(
            "Confirm Delete", "Are you sure you want to delete this access rule?"
        ):
            try:
                del self.acl_data["acls"][index]
                self.selected_edge_id = None
                self.setup_inspector_empty()
                self.trigger_refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ---- NODE CREATION ----
    def add_tag_node(self):
        dialog = ctk.CTkInputDialog(text="Tag Name (e.g. webserver):", title="Add Tag")
        val = dialog.get_input()
        if val:
            val = val.strip()
            if not val.startswith("tag:"):
                val = f"tag:{val}"

            self.acl_data.setdefault("tagOwners", {})
            if val not in self.acl_data["tagOwners"]:
                self.acl_data["tagOwners"][val] = ["autogroup:admin"]

                # Place node near center of canvas view
                cx = self.canvas.canvasx(self.canvas.winfo_width() / 2)
                cy = self.canvas.canvasy(self.canvas.winfo_height() / 2)
                self.nodes[val] = Node(val, val, "tag", cx - 90, cy - 45)
                self.coordinate_cache[val] = (cx - 90, cy - 45)

                self.trigger_refresh()
                self.select_node(val)

    def add_group_node(self):
        dialog = ctk.CTkInputDialog(
            text="Group Name (e.g. engineering):", title="Add Group"
        )
        val = dialog.get_input()
        if val:
            val = val.strip()
            if not val.startswith("group:"):
                val = f"group:{val}"

            self.acl_data.setdefault("groups", {})
            if val not in self.acl_data["groups"]:
                self.acl_data["groups"][val] = []

                cx = self.canvas.canvasx(self.canvas.winfo_width() / 2)
                cy = self.canvas.canvasy(self.canvas.winfo_height() / 2)
                self.nodes[val] = Node(val, val, "group", cx - 90, cy - 45)
                self.coordinate_cache[val] = (cx - 90, cy - 45)

                self.trigger_refresh()
                self.select_node(val)

    def add_user_node(self):
        dialog = ctk.CTkInputDialog(
            text="User Email (e.g. user@domain.com):", title="Add User"
        )
        val = dialog.get_input()
        if val:
            val = val.strip()
            # Users aren't standalone in json structure, but we can display them
            # if we make a mock user node, or let the user choose a group to add them to.
            # Here we create a node representing the user, and if they drag/connect to a group,
            # we add the user to that group.
            if val not in self.nodes:
                cx = self.canvas.canvasx(self.canvas.winfo_width() / 2)
                cy = self.canvas.canvasy(self.canvas.winfo_height() / 2)
                self.nodes[val] = Node(val, val, "user", cx - 90, cy - 45)
                self.added_users.add(val)
                self.coordinate_cache[val] = (cx - 90, cy - 45)
                self.redraw_canvas()
                self.select_node(val)

    # ---- PARSING DATA INTO GRAPH ----
    def load_data(self, acl_data, filepath=None):
        if filepath != self.loaded_filepath:
            self.added_users.clear()
            self.coordinate_cache.clear()
        self.acl_data = acl_data
        self.loaded_filepath = filepath
        self.selected_node_id = None
        self.selected_edge_id = None
        self.connected_nodes_set = set()
        self.connected_edges_set = set()
        self.visual_dim_levels = {}
        self.setup_inspector_empty()

        # 1. Gather all nodes preserving existing coords if loaded
        old_nodes = self.nodes
        self.nodes = {}

        # Add Autogroups
        autogroups = ["autogroup:admin", "autogroup:member"]
        for ag in autogroups:
            self.nodes[ag] = Node(ag, ag, "autogroup")

        # Add Groups
        for g, users in self.acl_data.get("groups", {}).items():
            self.nodes[g] = Node(g, g, "group", details={"members": users})

            # Add member users as nodes
            if self.show_group_members.get():
                for u in users:
                    if u not in self.nodes:
                        self.nodes[u] = Node(u, u, "user")

        # Add Users referenced directly in ACL sources
        if self.show_group_members.get():
            for r in self.acl_data.get("acls", []):
                for s in r.get("src", []):
                    if "@" in s and s not in self.nodes:
                        self.nodes[s] = Node(s, s, "user")

        # Add manually added user nodes that aren't yet in any group
        if self.show_group_members.get():
            for u in self.added_users:
                if u not in self.nodes:
                    self.nodes[u] = Node(u, u, "user")

        # Add Users referenced as tag owners in tagOwners
        if self.show_group_members.get():
            for t, owners in self.acl_data.get("tagOwners", {}).items():
                for o in owners:
                    if "@" in o and o not in self.nodes:
                        self.nodes[o] = Node(o, o, "user")

        # Add Tags from owners
        for t, owners in self.acl_data.get("tagOwners", {}).items():
            self.nodes[t] = Node(t, t, "tag", details={"owners": owners})

            # Load any group owner that wasn't defined in the main groups dict
            for o in owners:
                if o.startswith("group:") and o not in self.nodes:
                    self.nodes[o] = Node(o, o, "group", details={"members": []})

        # Add Tags referenced in ACL destinations
        for r in self.acl_data.get("acls", []):
            for d in r.get("dst", []):
                tag_part = d.rsplit(":", 1)[0]
                if tag_part.startswith("tag:") and tag_part not in self.nodes:
                    self.nodes[tag_part] = Node(
                        tag_part, tag_part, "tag", details={"owners": []}
                    )

        # Load Devices
        if self.show_devices.get():
            devices = self.get_devices_list()
            for dev in devices:
                dev_id = f"device:{dev['hostname']}"
                dev_tags = dev.get("tags", [])
                dev_owner = dev.get("owner", "")
                self.nodes[dev_id] = Node(
                    dev_id,
                    dev["hostname"],
                    "device",
                    details={
                        "ips": dev.get("ips", []),
                        "os": dev.get("os", "Unknown"),
                        "status": dev.get("status", "Offline"),
                        "owner": dev_owner,
                        "tags": dev_tags,
                    },
                )

        # Carry over positions
        raw_data = self.load_positions_file() or {}
        positions = (
            raw_data.get("positions", raw_data)
            if isinstance(raw_data, dict)
            else raw_data
        )

        # Load custom column ordering if present
        if isinstance(raw_data, dict) and "custom_column_orders" in raw_data:
            self.custom_column_orders = raw_data.get("custom_column_orders", {})

        # Merge file positions with coordinate cache
        for nid, pos in positions.items():
            self.coordinate_cache[nid] = pos

        for nid, node in self.nodes.items():
            if nid in self.coordinate_cache:
                node.x, node.y = self.coordinate_cache[nid]
            elif nid in old_nodes:
                node.x, node.y = old_nodes[nid].x, old_nodes[nid].y
                self.coordinate_cache[nid] = (node.x, node.y)

        # Check if we have any saved/cached coordinates across the whole graph
        has_positions = any(node.x != 0 or node.y != 0 for node in self.nodes.values())
        if not has_positions:
            self.apply_auto_layout(save=False)
        else:
            # Position only the new/revealed nodes that have no coordinates
            self.layout_new_nodes()

        self.rebuild_edges()
        self._update_scroll_region()
        self.redraw_canvas()

    def layout_new_nodes(self):
        col_x = {"device": 80, "user": 360, "autogroup": 360, "group": 640, "tag": 920}
        y_start = 80
        y_gap = 120

        # Group existing nodes by column to find their y coordinates
        col_ys = {}
        for node in self.nodes.values():
            if node.x != 0 or node.y != 0:
                col = col_x.get(node.type, 360)
                col_ys.setdefault(col, []).append(node.y)

        # Now place new nodes (x == 0 and y == 0)
        for nid, node in self.nodes.items():
            if node.x == 0 and node.y == 0:
                col = col_x.get(node.type, 360)
                existing_ys = col_ys.get(col, [])
                if existing_ys:
                    new_y = max(existing_ys) + y_gap
                else:
                    new_y = y_start
                node.x = col
                node.y = new_y
                col_ys.setdefault(col, []).append(new_y)
                self.coordinate_cache[nid] = (col, new_y)

    def rebuild_edges(self):
        self.edges = []

        # 1. ACL Rules
        if self.show_acl_rules.get():
            for idx, r in enumerate(self.acl_data.get("acls", [])):
                for s in r.get("src", []):
                    for d in r.get("dst", []):
                        dst_target, dst_ports = (
                            d.rsplit(":", 1) if ":" in d else (d, "*")
                        )

                        # Generate unique edge ID
                        edge_id = f"acl:{idx}:{s}->{dst_target}"

                        if s in self.nodes and dst_target in self.nodes:
                            self.edges.append(
                                Edge(
                                    edge_id,
                                    s,
                                    dst_target,
                                    "acl",
                                    ports=dst_ports,
                                    rule_index=idx,
                                )
                            )

        # 2. Group Memberships
        if self.show_group_members.get():
            for g, users in self.acl_data.get("groups", {}).items():
                for u in users:
                    if u in self.nodes and g in self.nodes:
                        self.edges.append(Edge(f"member:{u}->{g}", u, g, "membership"))

        # 3. Tag Owners
        if self.show_tag_owners.get():
            for t, owners in self.acl_data.get("tagOwners", {}).items():
                for o in owners:
                    if o in self.nodes and t in self.nodes:
                        self.edges.append(Edge(f"owner:{o}->{t}", o, t, "ownership"))

        # 4. Device Associations
        if self.show_devices.get():
            for nid, node in self.nodes.items():
                if node.type == "device":
                    dev_tags = node.details.get("tags", [])
                    dev_owner = node.details.get("owner", "")

                    connected = False
                    # Connect device to its tags
                    for t in dev_tags:
                        if t in self.nodes:
                            self.edges.append(
                                Edge(f"device_tag:{nid}->{t}", nid, t, "device")
                            )
                            connected = True

                    # Or connect device to its owner user node
                    if not connected and dev_owner and dev_owner in self.nodes:
                        self.edges.append(
                            Edge(
                                f"device_owner:{nid}->{dev_owner}",
                                nid,
                                dev_owner,
                                "device",
                            )
                        )

    def get_devices_list(self):
        """Attempts to parse live devices from CLI or falls back to reading Devices.md"""
        devices = []
        # First try Tailscale CLI
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                import json as _json

                data = _json.loads(result.stdout)
                peers = data.get("Peer", {})
                self_node = data.get("Self", {})
                user_map = data.get("User", {})

                def resolve_owner(node):
                    uid = node.get("UserID", node.get("User", 0))
                    if isinstance(uid, int) and uid != 0:
                        user_entry = user_map.get(str(uid), {})
                        login = user_entry.get("LoginName", "")
                        if login:
                            return login
                    if isinstance(uid, str) and uid:
                        return uid
                    return ""

                def parse_dev(node, label=""):
                    host = (
                        f"{node.get('HostName', 'Unknown')} ({label})"
                        if label
                        else node.get("HostName", "Unknown")
                    )
                    ips = node.get("TailscaleIPs", [""])
                    os_type = node.get("OS", "Unknown")
                    tags = node.get("Tags") or []
                    owner = resolve_owner(node)
                    return {
                        "hostname": host,
                        "ips": ips,
                        "owner": owner,
                        "os": os_type,
                        "status": "Active"
                        if node.get("Active", False) or label == "Self"
                        else "Offline",
                        "tags": tags,
                    }

                devices = [parse_dev(self_node, "Self")]
                for v in peers.values():
                    devices.append(parse_dev(v))
                # Write MD file if it doesn't exist
                md_path = "Tailscale Devices.md"
                if not os.path.exists(md_path):
                    self._write_devices_md(devices, md_path)
                return devices
        except Exception:
            pass

        # Fallback parsing of MD table
        md_path = "Tailscale Devices.md"
        if os.path.exists(md_path):
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if (
                            line.startswith("|")
                            and "IP Address" not in line
                            and "---" not in line
                        ):
                            parts = [p.strip() for p in line.split("|") if p.strip()]
                            if len(parts) >= 4:
                                # Hostname might contain status details, clean it
                                host = parts[1].split()[0]
                                os_type = parts[3].lower()
                                status_str = parts[4] if len(parts) > 4 else "Offline"
                                ip = parts[0]
                                owner = parts[2]

                                # Expand truncated owner email from Devices.md (e.g. "reid.sutton@" -> "reid.sutton@shinertechnologies.com")
                                if owner and owner != "tagged-devices":
                                    if owner.endswith("@"):
                                        owner = owner + "shinertechnologies.com"
                                    elif "@" not in owner:
                                        owner = owner + "@shinertechnologies.com"

                                # Assign tags for visualization
                                tags = []
                                if (
                                    len(parts) >= 6
                                    and parts[5]
                                    and parts[5].strip() != "-"
                                ):
                                    t_list = [
                                        t.strip()
                                        for t in parts[5].split(",")
                                        if t.strip()
                                    ]
                                    for t in t_list:
                                        if t.startswith("tag:"):
                                            tags.append(t)
                                        else:
                                            tags.append(f"tag:{t}")

                                # If no explicit tags, use heuristics
                                if not tags:
                                    if owner == "tagged-devices":
                                        if "server" in host.lower():
                                            tags.append("tag:dgx-server")
                                        elif (
                                            "standard" in host.lower()
                                            or "client" in host.lower()
                                        ):
                                            tags.append("tag:dgx-client")
                                        else:
                                            tags.append("tag:ai-agent")
                                    else:
                                        # User-owned devices only get tagged if hostname explicitly dictates it
                                        if (
                                            "dgx-server" in host.lower()
                                            or "dgxserver" in host.lower()
                                        ):
                                            tags.append("tag:dgx-server")
                                        elif "nickpeterson-client" in host.lower():
                                            tags.append("tag:nickpeterson-client")
                                        elif "nickpeterson-server" in host.lower():
                                            tags.append("tag:nickpeterson-server")
                                        elif (
                                            "ern-client" in host.lower()
                                            or "ernclient" in host.lower()
                                        ):
                                            tags.append("tag:ern-client")

                                devices.append(
                                    {
                                        "hostname": host,
                                        "ips": [ip],
                                        "owner": owner,
                                        "os": os_type,
                                        "status": status_str,
                                        "tags": tags,
                                    }
                                )
            except Exception:
                pass
        return devices

    def _write_devices_md(self, devices, path):
        """Write a list of device dicts to a Markdown table file."""
        header = "| IP Address | Hostname | Owner | OS | Status | Tags |"
        sep = "|---|---|---|---|---|---|"
        rows = []
        for dev in devices:
            ip = (dev.get("ips") or [""])[0]
            hostname = dev.get("hostname", "Unknown")
            owner = dev.get("owner", "")
            os_type = dev.get("os", "Unknown")
            status = dev.get("status", "-")
            tags = dev.get("tags", [])
            tags_str = ", ".join(tags) if tags else "-"
            rows.append(
                f"| {ip} | {hostname} | {owner} | {os_type} | {status} | {tags_str} |"
            )
        content = f"# Tailscale Devices\n\n{header}\n{sep}\n" + "\n".join(rows) + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    # ---- LAYOUT & PERSISTENCE ----
    def apply_auto_layout(self, save=True):
        # 1. Group nodes into logical columns (Devices on the left)
        col0_nodes = []  # Devices (Leftmost) - may span 2 sub-columns
        col1_nodes = []  # Users & Autogroups
        col2_nodes = []  # Groups
        col3_nodes = []  # Tags

        for nid, node in self.nodes.items():
            if node.type == "device":
                col0_nodes.append(nid)
            elif node.type in ["user", "autogroup"]:
                col1_nodes.append(nid)
            elif node.type == "group":
                col2_nodes.append(nid)
            elif node.type == "tag":
                col3_nodes.append(nid)

        # Sort devices, groups, tags alphabetically — unless custom order exists
        col2_nodes.sort()
        col3_nodes.sort()

        # --- Apply custom ordering per column if saved ---
        def _apply_custom_order(col_key, col_nodes):
            if col_key in self.custom_column_orders:
                saved = self.custom_column_orders[col_key]
                saved = [nid for nid in saved if nid in self.nodes]
                for nid in col_nodes:
                    if nid not in saved:
                        saved.append(nid)
                return [nid for nid in saved if nid in set(col_nodes)]
            return col_nodes

        # Custom ordering for groups
        col2_nodes = _apply_custom_order("groups", col2_nodes)
        # Custom ordering for tags
        col3_nodes = _apply_custom_order("tags", col3_nodes)

        # Default device sort: group by owner (alphabetically), then by hostname
        # Always uses owner-based sort — custom device order is separate
        col0_nodes = sorted(
            col0_nodes,
            key=lambda nid: (
                self.nodes[nid].details.get("owner", "(unowned)"),
                nid,
            ),
        )

        # Apply custom ordering for users column if saved
        if "users" in self.custom_column_orders:
            saved_order = self.custom_column_orders["users"]
            # Filter to only nodes that still exist
            saved_order = [nid for nid in saved_order if nid in self.nodes]
            # Add any new users not yet in custom order
            for nid in col1_nodes:
                if nid not in saved_order:
                    saved_order.append(nid)
            # Trim to match current col1_nodes
            filtered = set(col1_nodes)
            col1_nodes = [nid for nid in saved_order if nid in filtered]
        else:
            # Sort users by device ownership count (least to most)
            device_list = self.get_devices_list()
            user_device_counts = {}
            for dev in device_list:
                owner = dev.get("owner", "")
                if owner and "@" in owner:
                    user_device_counts[owner] = user_device_counts.get(owner, 0) + 1

            def user_sort_key(nid):
                node = self.nodes[nid]
                if node.type == "autogroup":
                    return (0, nid)
                count = user_device_counts.get(nid, 0)
                return (1, count, nid)

            col1_nodes.sort(key=user_sort_key)

        y_start = 80
        y_gap = 120

        # --- Devices: split into two sub-columns if there are more than 10 ---
        max_per_device_col = 10
        dev_col_x = [80, 240]  # two device sub-columns
        for i, nid in enumerate(col0_nodes):
            sub_col = i // max_per_device_col  # 0 or 1
            sub_col = min(sub_col, len(dev_col_x) - 1)
            cx = dev_col_x[sub_col]
            row = i % max_per_device_col
            self.nodes[nid].x = cx
            self.nodes[nid].y = y_start + row * y_gap
            self.coordinate_cache[nid] = (cx, y_start + row * y_gap)

        # Shift right columns further right if devices took 2 sub-columns
        device_cols_used = 2 if len(col0_nodes) > max_per_device_col else 1
        base_x = 80 + device_cols_used * 180  # 260 or 440

        col_x_right = [base_x, base_x + 280, base_x + 560]
        for col_idx, nids in enumerate([col1_nodes, col2_nodes, col3_nodes]):
            cx = col_x_right[col_idx]
            for i, nid in enumerate(nids):
                self.nodes[nid].x = cx
                self.nodes[nid].y = y_start + i * y_gap
                self.coordinate_cache[nid] = (cx, y_start + i * y_gap)

        self.rebuild_edges()
        self._update_scroll_region()
        self.redraw_canvas()

        if save:
            self.save_positions()

    def _update_scroll_region(self):
        """Expands the canvas scrollregion to always contain all node positions."""
        if not self.nodes:
            return
        max_x = max((n.x for n in self.nodes.values()), default=0) + 400
        max_y = max((n.y for n in self.nodes.values()), default=0) + 400
        # Never shrink below a reasonable minimum
        max_x = max(max_x, 2000)
        max_y = max(max_y, 2000)
        self.canvas.configure(scrollregion=(0, 0, max_x, max_y))

    def get_positions_filepath(self):
        if self.loaded_filepath:
            return f"{self.loaded_filepath}.positions.json"
        return "Tailscale Access Controls.positions.json"

    def load_positions_file(self):
        path = self.get_positions_filepath()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def save_positions(self):
        path = self.get_positions_filepath()
        positions = {nid: [node.x, node.y] for nid, node in self.nodes.items()}
        data = {
            "positions": positions,
            "custom_column_orders": self.custom_column_orders,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save layout: {e}")

    def zoom_in(self):
        factors = [0.5, 0.75, 1.0, 1.25, 1.5]
        try:
            curr_idx = factors.index(self.zoom_factor)
            if curr_idx < len(factors) - 1:
                self.zoom_factor = factors[curr_idx + 1]
                self.lbl_zoom.configure(text=f"{int(self.zoom_factor * 100)}%")
                self.update_canvas_scrollregion()
                self.redraw_canvas()
        except ValueError:
            self.zoom_factor = 1.0
            self.lbl_zoom.configure(text="100%")
            self.update_canvas_scrollregion()
            self.redraw_canvas()

    def zoom_out(self):
        factors = [0.5, 0.75, 1.0, 1.25, 1.5]
        try:
            curr_idx = factors.index(self.zoom_factor)
            if curr_idx > 0:
                self.zoom_factor = factors[curr_idx - 1]
                self.lbl_zoom.configure(text=f"{int(self.zoom_factor * 100)}%")
                self.update_canvas_scrollregion()
                self.redraw_canvas()
        except ValueError:
            self.zoom_factor = 1.0
            self.lbl_zoom.configure(text="100%")
            self.update_canvas_scrollregion()
            self.redraw_canvas()

    def update_canvas_scrollregion(self):
        base_w, base_h = 3000, 2400
        w = int(base_w * self.zoom_factor)
        h = int(base_h * self.zoom_factor)
        self.canvas.configure(scrollregion=(0, 0, w, h))

    def blend_color(self, hex_color, factor, bg_color="#0f172a"):
        if factor <= 0.0:
            return hex_color
        if factor >= 1.0:
            return bg_color

        color_map = {
            "white": "#ffffff",
            "black": "#000000",
            "red": "#ff0000",
            "green": "#00ff00",
            "blue": "#0000ff",
        }
        hex_color = color_map.get(hex_color.lower(), hex_color)
        bg_color = color_map.get(bg_color.lower(), bg_color)

        if not hex_color.startswith("#") or not bg_color.startswith("#"):
            return hex_color

        try:
            h_color = hex_color.lstrip("#")
            r1, g1, b1 = (
                int(h_color[0:2], 16),
                int(h_color[2:4], 16),
                int(h_color[4:6], 16),
            )

            b_color = bg_color.lstrip("#")
            r2, g2, b2 = (
                int(b_color[0:2], 16),
                int(b_color[2:4], 16),
                int(b_color[4:6], 16),
            )

            r = int(r1 + (r2 - r1) * factor)
            g = int(g1 + (g2 - g1) * factor)
            b = int(b1 + (b2 - b1) * factor)

            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def update_connected_sets(self):
        self.connected_nodes_set = set()
        self.connected_edges_set = set()

        if self.selected_node_id:
            self.connected_nodes_set.add(self.selected_node_id)
            for e in self.edges:
                if e.src_id == self.selected_node_id:
                    self.connected_edges_set.add(e.id)
                    self.connected_nodes_set.add(e.dst_id)
                elif e.dst_id == self.selected_node_id:
                    self.connected_edges_set.add(e.id)
                    self.connected_nodes_set.add(e.src_id)

        elif self.selected_edge_id:
            self.connected_edges_set.add(self.selected_edge_id)
            for e in self.edges:
                if e.id == self.selected_edge_id:
                    self.connected_nodes_set.add(e.src_id)
                    self.connected_nodes_set.add(e.dst_id)
                    break

    def start_dimming_animation(self):
        if not self.animating_dim:
            self.animating_dim = True
            self.animate_dimming_step()

    def animate_dimming_step(self):
        step = 0.15
        changed = False

        # Nodes
        for nid in self.nodes:
            curr = self.visual_dim_levels.get(nid, 0.0)
            target = (
                0.75
                if (
                    (self.selected_node_id or self.selected_edge_id)
                    and nid not in self.connected_nodes_set
                )
                else 0.0
            )
            if abs(curr - target) > 0.01:
                if curr < target:
                    curr = min(target, curr + step)
                else:
                    curr = max(target, curr - step)
                self.visual_dim_levels[nid] = curr
                changed = True

        # Edges
        for e in self.edges:
            curr = self.visual_dim_levels.get(e.id, 0.0)
            target = (
                0.75
                if (
                    (self.selected_node_id or self.selected_edge_id)
                    and e.id not in self.connected_edges_set
                )
                else 0.0
            )
            if abs(curr - target) > 0.01:
                if curr < target:
                    curr = min(target, curr + step)
                else:
                    curr = max(target, curr - step)
                self.visual_dim_levels[e.id] = curr
                changed = True

        if changed:
            self.redraw_canvas()
            self.after(20, self.animate_dimming_step)
        else:
            self.animating_dim = False

    # ---- RENDERING LOGIC ----
    def redraw_canvas(self):
        self.canvas.delete("all")

        # 1. Draw Grid Background
        self.draw_grid()

        # 2. Draw Edges
        for e in self.edges:
            self.draw_edge(e)

        # 3. Draw Nodes
        for nid in self.nodes:
            self.draw_node_visual(nid)

    def draw_grid(self):
        w, h = 3000, 2400
        step = int(40 * self.zoom_factor)
        for x in range(0, w, step):
            self.canvas.create_line(x, 0, x, h, fill="#1e293b", tags="grid")
        for y in range(0, h, step):
            self.canvas.create_line(0, y, w, y, fill="#1e293b", tags="grid")

    def draw_node_visual(self, node_id):
        self.canvas.delete(f"node_visual:{node_id}")
        node = self.nodes[node_id]
        x = node.x * self.zoom_factor
        y = node.y * self.zoom_factor
        w = node.width * self.zoom_factor
        h = node.height * self.zoom_factor

        df = self.visual_dim_levels.get(node_id, 0.0)

        # Colors matching modern sleek developer theme
        colors = {
            "user": ("#0ea5e9", "#0284c7"),  # Sky Blue
            "group": ("#8b5cf6", "#7c3aed"),  # Purple/Violet
            "tag": ("#f97316", "#ea580c"),  # Orange
            "autogroup": ("#10b981", "#059669"),  # Emerald
            "device": ("#64748b", "#475569"),  # Slate
        }
        header_base, border_base = colors.get(node.type, ("#64748b", "#475569"))

        header_color = self.blend_color(header_base, df)
        border_color = self.blend_color(border_base, df)

        # 1. Shadow (offset outline rectangle)
        self.canvas.create_rectangle(
            x + 4 * self.zoom_factor,
            y + 4 * self.zoom_factor,
            x + w + 4 * self.zoom_factor,
            y + h + 4 * self.zoom_factor,
            fill=self.blend_color("#020617", df),
            outline="",
            tags=(f"node_visual:{node_id}", f"shadow:{node_id}", "shadow"),
        )

        # 2. Main Box
        bg_color = self.blend_color("#1e293b", df)
        is_selected = self.selected_node_id == node_id
        border_width = 3 if is_selected else 2
        active_border = self.blend_color(
            "#06b6d4" if is_selected else border_base, df
        )  # Cyan outline if selected

        self.canvas.create_rectangle(
            x,
            y,
            x + w,
            y + h,
            fill=bg_color,
            outline=active_border,
            width=border_width,
            tags=(f"node_visual:{node_id}", f"node:{node_id}", "node_box"),
        )

        # 3. Header
        self.canvas.create_rectangle(
            x + border_width,
            y + border_width,
            x + w - border_width,
            y + 24 * self.zoom_factor,
            fill=header_color,
            outline="",
            tags=(f"node_visual:{node_id}", f"node:{node_id}", "node_header"),
        )

        # 4. Text Display
        disp_title = node.name
        if len(disp_title) > 22:
            disp_title = disp_title[:19] + "..."

        font_size_bold = int(9 * self.zoom_factor)
        font_size_normal = int(8 * self.zoom_factor)
        if font_size_bold < 6:
            font_size_bold = 6
        if font_size_normal < 5:
            font_size_normal = 5

        self.canvas.create_text(
            x + 8 * self.zoom_factor,
            y + 13 * self.zoom_factor,
            text=disp_title,
            fill=self.blend_color("#ffffff", df),
            font=("Segoe UI", font_size_bold, "bold"),
            anchor="w",
            tags=(f"node_visual:{node_id}", f"node:{node_id}", "node_title"),
        )

        content_y = y + 36 * self.zoom_factor

        text_lbl_color = self.blend_color("#94a3b8", df)
        text_sub_color = self.blend_color("#cbd5e1", df)
        text_muted_color = self.blend_color("#64748b", df)

        if node.type == "group":
            members = node.details.get("members", [])
            self.canvas.create_text(
                x + 8 * self.zoom_factor,
                content_y,
                text=f"Members ({len(members)}):",
                fill=text_lbl_color,
                font=("Segoe UI", font_size_normal, "bold"),
                anchor="w",
                tags=(f"node_visual:{node_id}", f"node:{node_id}"),
            )
            for i, m in enumerate(members[:2]):
                disp_m = m
                if len(disp_m) > 23:
                    disp_m = disp_m[:20] + "..."
                self.canvas.create_text(
                    x + 8 * self.zoom_factor,
                    content_y + (14 + i * 12) * self.zoom_factor,
                    text=f"- {disp_m}",
                    fill=text_sub_color,
                    font=("Segoe UI", font_size_normal),
                    anchor="w",
                    tags=(f"node_visual:{node_id}", f"node:{node_id}"),
                )
            if len(members) > 2:
                self.canvas.create_text(
                    x + 8 * self.zoom_factor,
                    content_y + 38 * self.zoom_factor,
                    text=f"  ...and {len(members) - 2} more",
                    fill=text_muted_color,
                    font=("Segoe UI", font_size_normal, "italic"),
                    anchor="w",
                    tags=(f"node_visual:{node_id}", f"node:{node_id}"),
                )

        elif node.type == "tag":
            owners = node.details.get("owners", [])
            self.canvas.create_text(
                x + 8 * self.zoom_factor,
                content_y,
                text=f"Owners ({len(owners)}):",
                fill=text_lbl_color,
                font=("Segoe UI", font_size_normal, "bold"),
                anchor="w",
                tags=(f"node_visual:{node_id}", f"node:{node_id}"),
            )
            disp_o = ", ".join([o.replace("group:", "") for o in owners[:2]])
            if len(disp_o) > 22:
                disp_o = disp_o[:19] + "..."
            self.canvas.create_text(
                x + 8 * self.zoom_factor,
                content_y + 14 * self.zoom_factor,
                text=disp_o or "(none)",
                fill=text_sub_color,
                font=("Segoe UI", font_size_normal),
                anchor="w",
                tags=(f"node_visual:{node_id}", f"node:{node_id}"),
            )
            if len(owners) > 2:
                self.canvas.create_text(
                    x + 8 * self.zoom_factor,
                    content_y + 26 * self.zoom_factor,
                    text=f"...and {len(owners) - 2} more",
                    fill=text_muted_color,
                    font=("Segoe UI", font_size_normal, "italic"),
                    anchor="w",
                    tags=(f"node_visual:{node_id}", f"node:{node_id}"),
                )

        elif node.type == "device":
            ips = node.details.get("ips", [])
            os_name = node.details.get("os", "Unknown")
            status = node.details.get("status", "Offline")

            self.canvas.create_text(
                x + 8 * self.zoom_factor,
                content_y,
                text=f"IP: {ips[0] if ips else 'None'}",
                fill=text_sub_color,
                font=("Segoe UI", font_size_normal),
                anchor="w",
                tags=(f"node_visual:{node_id}", f"node:{node_id}"),
            )
            self.canvas.create_text(
                x + 8 * self.zoom_factor,
                content_y + 14 * self.zoom_factor,
                text=f"OS: {os_name}",
                fill=text_sub_color,
                font=("Segoe UI", font_size_normal),
                anchor="w",
                tags=(f"node_visual:{node_id}", f"node:{node_id}"),
            )

            is_act = "active" in status or "idle" in status or status == "-"
            self.canvas.create_text(
                x + 8 * self.zoom_factor,
                content_y + 28 * self.zoom_factor,
                text="Active" if is_act else "Offline",
                fill=self.blend_color("#10b981" if is_act else "#64748b", df),
                font=("Segoe UI", font_size_normal, "bold"),
                anchor="w",
                tags=(f"node_visual:{node_id}", f"node:{node_id}"),
            )

        else:  # user or autogroup
            if node.type == "user":
                # Show which groups this user belongs to (instead of repeating full email)
                user_groups = [
                    g
                    for g, members in self.acl_data.get("groups", {}).items()
                    if node.id in members
                ]
                if user_groups:
                    disp_g = user_groups[0].replace("group:", "")
                    if len(disp_g) > 20:
                        disp_g = disp_g[:17] + "..."
                    self.canvas.create_text(
                        x + 8 * self.zoom_factor,
                        content_y,
                        text=f"in: {disp_g}",
                        fill=text_sub_color,
                        font=("Segoe UI", font_size_normal),
                        anchor="w",
                        tags=(f"node_visual:{node_id}", f"node:{node_id}"),
                    )
                    if len(user_groups) > 1:
                        self.canvas.create_text(
                            x + 8 * self.zoom_factor,
                            content_y + 12 * self.zoom_factor,
                            text=f"  +{len(user_groups) - 1} more group(s)",
                            fill=text_muted_color,
                            font=("Segoe UI", font_size_normal, "italic"),
                            anchor="w",
                            tags=(f"node_visual:{node_id}", f"node:{node_id}"),
                        )
                else:
                    self.canvas.create_text(
                        x + 8 * self.zoom_factor,
                        content_y,
                        text="No group membership",
                        fill=text_muted_color,
                        font=("Segoe UI", font_size_normal, "italic"),
                        anchor="w",
                        tags=(f"node_visual:{node_id}", f"node:{node_id}"),
                    )
            else:  # autogroup
                self.canvas.create_text(
                    x + 8 * self.zoom_factor,
                    content_y,
                    text="Built-in Tailscale group",
                    fill=text_muted_color,
                    font=("Segoe UI", font_size_normal, "italic"),
                    anchor="w",
                    tags=(f"node_visual:{node_id}", f"node:{node_id}"),
                )

        # 5. Connectors (Pins)
        pin_fill = self.blend_color("#10b981", df)
        pin_outline = self.blend_color("#ffffff", df)
        # Outputs on Right Edge Center
        if node.type in ["user", "group", "tag", "autogroup"]:
            ox, oy = x + w, y + h / 2
            r = 5 * self.zoom_factor
            self.canvas.create_oval(
                ox - r,
                oy - r,
                ox + r,
                oy + r,
                fill=pin_fill,
                outline=pin_outline,
                width=1,
                tags=(f"node_visual:{node_id}", f"pin_out:{node_id}", "pin_out", "pin"),
            )

        # Inputs on Left Edge Center
        if node.type in ["tag", "autogroup", "group"]:
            ix, iy = x, y + h / 2
            r = 5 * self.zoom_factor
            self.canvas.create_oval(
                ix - r,
                iy - r,
                ix + r,
                iy + r,
                fill=pin_fill,
                outline=pin_outline,
                width=1,
                tags=(f"node_visual:{node_id}", f"pin_in:{node_id}", "pin_in", "pin"),
            )

    def draw_edge(self, edge):
        self.canvas.delete(f"edge_visual:{edge.id}")
        src = self.nodes.get(edge.src_id)
        dst = self.nodes.get(edge.dst_id)
        if not src or not dst:
            return

        df = self.visual_dim_levels.get(edge.id, 0.0)

        # Base coordinates
        sx = (src.x + src.width) * self.zoom_factor
        sy = (src.y + src.height / 2) * self.zoom_factor
        dx = dst.x * self.zoom_factor
        dy = (dst.y + dst.height / 2) * self.zoom_factor

        # Self-loop: draw a semi-circular arc on the right side of the node
        if edge.src_id == edge.dst_id:
            loop_r = 30 * self.zoom_factor
            cx1 = sx + loop_r
            cy1 = sy - loop_r
            cx2 = sx + loop_r
            cy2 = sy + loop_r
            dx = sx
            dy = sy
        else:
            # Adjust links
            if src.type == "tag" and dst.type == "tag" and abs(src.x - dst.x) < 50:
                # Special loop for Tag-to-Tag connections in the same column
                # Loop out to the right side
                sx = (src.x + src.width) * self.zoom_factor
                sy = (src.y + src.height / 2) * self.zoom_factor
                dx = (dst.x + dst.width) * self.zoom_factor
                dy = (dst.y + dst.height / 2) * self.zoom_factor

                loop_offset = 100 * self.zoom_factor
                cx1 = sx + loop_offset
                cy1 = sy
                cx2 = dx + loop_offset
                cy2 = dy
            else:
                if edge.type == "membership":
                    dx, dy = (
                        dst.x * self.zoom_factor,
                        (dst.y + dst.height / 2) * self.zoom_factor,
                    )
                elif edge.type == "ownership":
                    dx, dy = (
                        dst.x * self.zoom_factor,
                        (dst.y + dst.height / 2) * self.zoom_factor,
                    )
                elif edge.type == "device":
                    sx = (src.x + src.width) * self.zoom_factor
                    sy = (src.y + src.height / 2) * self.zoom_factor
                    dx = dst.x * self.zoom_factor
                    dy = (dst.y + dst.height / 2) * self.zoom_factor

                # Bezier calculation
                dist = abs(dx - sx)
                offset = max(60 * self.zoom_factor, dist * 0.45)
                cx1 = sx + offset
                cy1 = sy
                cx2 = dx - offset
                cy2 = dy

        is_sel = self.selected_edge_id == edge.id

        # Styles
        if edge.type == "acl":
            base_color = "#06b6d4" if is_sel else "#10b981"  # Cyan vs Emerald
            width = 3 * self.zoom_factor if is_sel else 2 * self.zoom_factor
            dash = ()
            arrow = "last"
        elif edge.type == "membership":
            base_color = "#c084fc"  # Purple-400
            width = 1.5 * self.zoom_factor
            dash = (int(4 * self.zoom_factor), int(4 * self.zoom_factor))
            arrow = "last"
        elif edge.type == "ownership":
            base_color = "#f59e0b"  # Amber-500
            width = 1.5 * self.zoom_factor
            dash = (int(4 * self.zoom_factor), int(4 * self.zoom_factor))
            arrow = "last"
        else:  # device
            base_color = "#475569"  # Slate-600
            width = 1 * self.zoom_factor
            dash = ()
            arrow = "none"

        color = self.blend_color(base_color, df)

        self.canvas.create_line(
            sx,
            sy,
            cx1,
            cy1,
            cx2,
            cy2,
            dx,
            dy,
            smooth=True,
            fill=color,
            width=width,
            dash=dash,
            arrow=arrow,
            arrowshape=(
                int(8 * self.zoom_factor),
                int(10 * self.zoom_factor),
                int(3 * self.zoom_factor),
            ),
            tags=(f"edge_visual:{edge.id}", f"edge:{edge.id}", "edge_line"),
        )

        # Port label badge
        if edge.type == "acl" and edge.ports:
            # Compute exact midpoint of the cubic Bezier curve (t = 0.5)
            mx = 0.125 * sx + 0.375 * cx1 + 0.375 * cx2 + 0.125 * dx
            my = 0.125 * sy + 0.375 * cy1 + 0.375 * cy2 + 0.125 * dy

            lbl_str = f":{edge.ports}"
            lbl_w = (len(lbl_str) * 6 + 10) * self.zoom_factor

            # Badge Background Box
            self.canvas.create_rectangle(
                mx - lbl_w / 2,
                my - 8 * self.zoom_factor,
                mx + lbl_w / 2,
                my + 8 * self.zoom_factor,
                fill=self.blend_color("#1e293b", df),
                outline=color,
                width=1,
                tags=(f"edge_visual:{edge.id}", f"edge:{edge.id}", "edge_badge"),
            )

            # Badge Text
            self.canvas.create_text(
                mx,
                my,
                text=lbl_str,
                fill=self.blend_color("#e2e8f0", df),
                font=("Consolas", int(8 * self.zoom_factor), "bold"),
                tags=(f"edge_visual:{edge.id}", f"edge:{edge.id}", "edge_badge_text"),
            )

    # ---- EVENT HANDLERS ----
    def on_canvas_press(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        # 1. Check if clicked a pin to start connecting (with a generous hit-test radius of 10px)
        items_pin = self.canvas.find_overlapping(cx - 10, cy - 10, cx + 10, cy + 10)
        for item in items_pin:
            tags = self.canvas.gettags(item)
            # Find output pin tag
            for tag in tags:
                if tag.startswith("pin_out:"):
                    src_node = tag.split(":", 1)[1]
                    self.conn_start_node_id = src_node
                    self.conn_start_x = cx
                    self.conn_start_y = cy
                    self.temp_conn_line = self.canvas.create_line(
                        cx, cy, cx, cy, fill="#e11d48", width=2, dash=(3, 3)
                    )
                    return

        # 2. Check if clicked a node box or any part of a node (with a generous hit-test radius of 10px)
        clicked_node_id = None
        for item in items_pin:
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith("node_visual:"):
                    clicked_node_id = tag.split(":", 1)[1]
                    break
            if clicked_node_id:
                break

        if clicked_node_id:
            self.select_node(clicked_node_id)
            # Setup dragging
            self.drag_node_id = clicked_node_id
            self.drag_start_x = cx
            self.drag_start_y = cy
            node = self.nodes[clicked_node_id]
            self.node_initial_x = node.x
            self.node_initial_y = node.y
            return

        # 3. Check if clicked an edge line
        clicked_edge_id = None
        for item in items_pin:
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith("edge:"):
                    clicked_edge_id = tag.split(":", 1)[1]
                    break
            if clicked_edge_id:
                break

        if clicked_edge_id:
            self.select_edge(clicked_edge_id)
            return

        # 4. Clicked blank background
        self.deselect_all()

    def on_canvas_drag(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        # Handle connection drawing drag
        if self.conn_start_node_id and self.temp_conn_line:
            self.canvas.coords(
                self.temp_conn_line, self.conn_start_x, self.conn_start_y, cx, cy
            )
            return

        # Handle node dragging
        if self.drag_node_id:
            dx = cx - self.drag_start_x
            dy = cy - self.drag_start_y

            node = self.nodes[self.drag_node_id]
            node.x = self.node_initial_x + dx / self.zoom_factor
            node.y = self.node_initial_y + dy / self.zoom_factor
            self.coordinate_cache[self.drag_node_id] = (node.x, node.y)

            # Reposition Visual Components
            self.redraw_node_items(self.drag_node_id)

            # Redraw Connected Edges
            for e in self.edges:
                if e.src_id == self.drag_node_id or e.dst_id == self.drag_node_id:
                    self.draw_edge(e)

    def on_canvas_release(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        # Connection Mode Resolution
        if self.conn_start_node_id and self.temp_conn_line:
            self.canvas.delete(self.temp_conn_line)
            self.temp_conn_line = None

            # Find destination node release target (with a generous 12px radius)
            dest_node_id = None
            items = self.canvas.find_overlapping(cx - 12, cy - 12, cx + 12, cy + 12)
            for item in items:
                tags = self.canvas.gettags(item)
                for tag in tags:
                    if tag.startswith("node_visual:"):
                        dest_node_id = tag.split(":", 1)[1]
                        break
                if dest_node_id:
                    break

            if dest_node_id:
                self.handle_visual_connection(self.conn_start_node_id, dest_node_id)

            self.conn_start_node_id = None
            return

        # Node Drag Release
        if self.drag_node_id:
            self.drag_node_id = None
            self.save_positions()

    def handle_visual_connection(self, src_id, dst_id):
        src = self.nodes.get(src_id)
        dst = self.nodes.get(dst_id)
        if not src or not dst:
            return

        # 1. Connect User node to Group node (Membership)
        if src.type == "user" and dst.type == "group":
            if src_id not in self.acl_data["groups"][dst_id]:
                self.acl_data["groups"][dst_id].append(src_id)
                self.trigger_refresh()
                self.select_node(dst_id)
            return

        # 2. Connect Group/User node to Tag node (Ownership or ACL)
        if (src.type in ["group", "user", "autogroup"]) and dst.type == "tag":
            # Ask whether they want to define Owner or an ACL Access Rule
            dialog = ConnectionLinkDialog(self.winfo_toplevel(), src.name, dst.name)
            choice = dialog.choice

            if choice == "acl":  # Access Rule
                self.create_acl_rule_dialog(src_id, dst_id)
            elif choice == "owner":  # Tag Owner
                if src_id not in self.acl_data["tagOwners"].get(dst_id, []):
                    self.acl_data.setdefault("tagOwners", {}).setdefault(
                        dst_id, []
                    ).append(src_id)
                    self.trigger_refresh()
                    self.select_node(dst_id)
            return

        # 3. Connection between Tag and Tag (ACL Access Rule)
        if src.type == "tag" and dst.type == "tag":
            self.create_acl_rule_dialog(src_id, dst_id)
            return

        # 4. Self-loop on autogroup (allow-by-default rule)
        if src.type == "autogroup" and src_id == dst_id:
            ports = "*"
            label = (
                src_id.replace("autogroup:", "autogroup").title()
                if "autogroup:" in src_id
                else src_id
            )
            dialog = ctk.CTkInputDialog(
                text=f"Allowed ports for {src_id} self-connection (allow-by-default)?\nDefault is '*':",
                title="Self-Connection Ports",
            )
            ports_input = dialog.get_input()
            if ports_input is not None:
                ports = ports_input.strip() or "*"
                self.acl_data.setdefault("acls", []).append(
                    {"action": "accept", "src": [src_id], "dst": [f"{src_id}:{ports}"]}
                )
                self.trigger_refresh()
                self.select_node(src_id)
            return

    def create_acl_rule_dialog(self, src_id, dst_id):
        # Prompt for ports using beautiful CTkInputDialog to prevent focus lock-up
        dialog = ctk.CTkInputDialog(
            text="Define allowed ports (e.g. *, 22, 80, 443)\nDefault is '*':",
            title="Access Ports",
        )
        ports = dialog.get_input()
        if ports is not None:
            ports = ports.strip() or "*"

            self.acl_data.setdefault("acls", []).append(
                {"action": "accept", "src": [src_id], "dst": [f"{dst_id}:{ports}"]}
            )
            self.trigger_refresh()

    def redraw_node_items(self, node_id):
        # Instead of redrawing everything, just move elements associated with node
        node = self.nodes[node_id]

        # We can find all elements with tag node_visual:node_id and delete/re-render only this node
        self.draw_node_visual(node_id)

    # ---- PANNING ----
    def on_pan_press(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def on_pan_drag(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    # ---- MOUSE HOVER PIN HANDLER ----
    def on_mouse_motion(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        items = self.canvas.find_overlapping(cx - 10, cy - 10, cx + 10, cy + 10)
        hovered_pin = None
        for item in items:
            tags = self.canvas.gettags(item)
            if "pin" in tags:
                hovered_pin = item
                break

        if hovered_pin:
            if self.last_hovered_pin and self.last_hovered_pin != hovered_pin:
                self.canvas.itemconfig(self.last_hovered_pin, fill="#10b981")
            self.canvas.itemconfig(hovered_pin, fill="#fbbf24")  # glow yellow
            self.last_hovered_pin = hovered_pin
        else:
            if self.last_hovered_pin:
                self.canvas.itemconfig(self.last_hovered_pin, fill="#10b981")
                self.last_hovered_pin = None

    def select_node(self, node_id):
        self.selected_edge_id = None
        self.selected_node_id = node_id

        self.update_connected_sets()
        self.start_dimming_animation()

        # Focus the canvas so arrow keys work after selection
        self.canvas.focus_set()

        if node_id:
            self.show_node_inspector(node_id)

    def select_edge(self, edge_id):
        self.selected_node_id = None
        self.selected_edge_id = edge_id

        self.update_connected_sets()
        self.start_dimming_animation()

        if edge_id:
            self.show_edge_inspector(edge_id)

    def deselect_all(self):
        self.selected_node_id = None
        self.selected_edge_id = None

        self.update_connected_sets()
        self.start_dimming_animation()

        self.setup_inspector_empty()

    def _get_column_key(self, node):
        """Return the column key for a node type."""
        if node.type == "device":
            return "device"
        elif node.type in ("user", "autogroup"):
            return "users"
        elif node.type == "group":
            return "groups"
        elif node.type == "tag":
            return "tags"
        return None

    def _move_selected_node_column(self, direction):
        """Move selected node up (-1) or down (+1) within its column."""
        # Ensure canvas has focus for subsequent key events
        self.canvas.focus_set()

        if not self.selected_node_id:
            return
        node = self.nodes.get(self.selected_node_id)
        if not node:
            return
        col_key = self._get_column_key(node)
        if not col_key:
            return
        # Ensure we have an ordering for this column
        if col_key not in self.custom_column_orders:
            self.custom_column_orders[col_key] = [
                nid
                for nid, n in self.nodes.items()
                if self._get_column_key(n) == col_key
            ]
        order = self.custom_column_orders[col_key]
        if node.id not in order:
            return
        idx = order.index(node.id)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(order):
            return
        # Swap
        order[idx], order[new_idx] = order[new_idx], order[idx]
        self.apply_auto_layout(save=False)
        # Re-select the node
        self.select_node(self.selected_node_id)

    def _on_key_column_up(self, event):
        self._move_selected_node_column(-1)

    def _on_key_column_down(self, event):
        self._move_selected_node_column(+1)

    # ---- HELPER / SYNCS ----
    def trigger_refresh(self):
        # Rebuild layout/edges from internal acl_data model
        self.load_data(self.acl_data, self.loaded_filepath)
        if self.refresh_callback:
            self.refresh_callback()

    def get_all_possible_owners(self):
        opts = list(self.acl_data.get("groups", {}).keys())
        opts.extend(["autogroup:admin", "autogroup:member"])
        return opts

    def on_mousewheel(self, event):
        if event.delta > 0:
            self.zoom_in()
        elif event.delta < 0:
            self.zoom_out()

    def on_vis_layer_changed(self):
        old_sel_node = self.selected_node_id
        old_sel_edge = self.selected_edge_id

        self.load_data(self.acl_data, self.loaded_filepath)

        if old_sel_node and old_sel_node in self.nodes:
            self.select_node(old_sel_node)
        elif old_sel_edge and any(e.id == old_sel_edge for e in self.edges):
            self.select_edge(old_sel_edge)
        else:
            self.deselect_all()
