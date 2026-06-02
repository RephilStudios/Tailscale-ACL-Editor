import json
import subprocess
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

import customtkinter as ctk
import json5
from topology_editor import TopologyEditor


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class CustomDialog(ctk.CTkToplevel):
    def __init__(
        self, parent, title, labels, options, show_ports=True, default_values=None
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry("450x350")
        self.result = None

        self.boxes = []
        for i, (lbl, opts) in enumerate(zip(labels, options)):
            ctk.CTkLabel(self, text=lbl, font=ctk.CTkFont(weight="bold")).pack(
                pady=(10, 0)
            )
            box = ctk.CTkComboBox(self, values=opts, width=350)
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
                text="Ports (e.g., '*', '80,443'):",
                font=ctk.CTkFont(weight="bold"),
            ).pack(pady=(10, 0))
            self.port_entry = ctk.CTkEntry(self, width=350)
            if default_values and len(default_values) > len(labels):
                self.port_entry.insert(0, default_values[-1])
            else:
                self.port_entry.insert(0, "*")
            self.port_entry.pack(pady=5)

        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(pady=20)
        ctk.CTkButton(btn_f, text="Submit", command=self.submit).pack(
            side="left", padx=10
        )
        ctk.CTkButton(btn_f, text="Cancel", fg_color="red", command=self.cancel).pack(
            side="left", padx=10
        )

        self.grab_set()

    def submit(self):
        res = [b.get() for b in self.boxes]
        if self.show_ports:
            res.append(self.port_entry.get())
        self.result = res
        self.destroy()

    def cancel(self):
        self.destroy()


class ACLManagerV5(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Tailscale Ultimate Dashboard v5.0 - Full CRUD")
        self.geometry("1200x800")

        self.acl_data = {"groups": {}, "tagOwners": {}, "acls": [], "ssh": []}
        self.current_tag = None
        self.current_filepath = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)
        ctk.CTkLabel(
            self.sidebar_frame,
            text="Ultimate Dashboard",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 10))
        ctk.CTkButton(
            self.sidebar_frame, text="Load Config", command=self.load_json
        ).grid(row=1, column=0, padx=20, pady=10)
        ctk.CTkButton(
            self.sidebar_frame, text="Save Config", command=self.save_json
        ).grid(row=2, column=0, padx=20, pady=10)
        self.lbl_status = ctk.CTkLabel(self.sidebar_frame, text="Ready.")
        self.lbl_status.grid(row=6, column=0, padx=20, pady=20)

        # Tabs
        self.main_frame = ctk.CTkTabview(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.tab_tags = self.main_frame.add("Network Tags")
        self.tab_rules = self.main_frame.add("Access Rules Builder")
        self.tab_groups = self.main_frame.add("Groups Manager")
        self.tab_devices = self.main_frame.add("Live Devices")
        self.tab_raw = self.main_frame.add("Raw JSON")
        self.tab_topology = self.main_frame.add("Topology Editor")

        self.setup_tags_tab()
        self.setup_rules_tab()
        self.setup_groups_tab()
        self.setup_devices_tab()
        self.setup_raw_tab()
        self.setup_topology_tab()
        self.autoload_last_config()

    # ---- SETUP ----
    def setup_tags_tab(self):
        self.tab_tags.grid_rowconfigure(0, weight=1)
        self.tab_tags.grid_columnconfigure(0, weight=1)
        self.tab_tags.grid_columnconfigure(1, weight=3)

        left_f = ctk.CTkFrame(self.tab_tags)
        left_f.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        ctk.CTkLabel(
            left_f, text="All Network Tags", font=ctk.CTkFont(weight="bold")
        ).pack(pady=10)
        self.tags_scrollable = ctk.CTkScrollableFrame(left_f)
        self.tags_scrollable.pack(fill="both", expand=True, padx=5, pady=5)
        ctk.CTkButton(left_f, text="+ Create New Tag", command=self.create_tag).pack(
            pady=10, padx=10, fill="x"
        )

        self.right_f = ctk.CTkFrame(self.tab_tags)
        self.right_f.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        header_f = ctk.CTkFrame(self.right_f, fg_color="transparent")
        header_f.pack(fill="x", pady=10)
        self.lbl_tag_title = ctk.CTkLabel(
            header_f, text="Select a tag", font=ctk.CTkFont(size=24, weight="bold")
        )
        self.lbl_tag_title.pack(side="left", padx=20)

        self.btn_rename_tag = ctk.CTkButton(
            header_f, text="Rename", width=80, command=self.rename_tag
        )
        self.btn_delete_tag = ctk.CTkButton(
            header_f, text="Delete", fg_color="red", width=80, command=self.delete_tag
        )

        self.f_owners = ctk.CTkFrame(self.right_f)
        self.f_owners.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(
            self.f_owners, text="Ownership", font=ctk.CTkFont(weight="bold")
        ).pack(pady=5)
        self.lbl_owners = ctk.CTkLabel(self.f_owners, text="")
        self.lbl_owners.pack()

        btn_own_f = ctk.CTkFrame(self.f_owners, fg_color="transparent")
        btn_own_f.pack(pady=5)
        self.btn_add_owner = ctk.CTkButton(
            btn_own_f, text="Add Owner", width=100, command=self.add_owner
        )
        self.btn_remove_owner = ctk.CTkButton(
            btn_own_f,
            text="Remove Owner",
            width=100,
            fg_color="red",
            command=self.remove_owner,
        )

        self.f_outbound = ctk.CTkFrame(self.right_f)
        self.f_outbound.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(
            self.f_outbound, text="Outbound Access", font=ctk.CTkFont(weight="bold")
        ).pack(pady=5)
        self.txt_outbound = ctk.CTkTextbox(self.f_outbound, height=100)
        self.txt_outbound.pack(fill="x", padx=10, pady=5)

        btn_out_f = ctk.CTkFrame(self.f_outbound, fg_color="transparent")
        btn_out_f.pack(pady=5)
        self.btn_add_outbound = ctk.CTkButton(
            btn_out_f,
            text="Add Outbound Rule",
            fg_color="green",
            width=120,
            command=self.add_outbound_rule,
        )
        self.btn_remove_outbound = ctk.CTkButton(
            btn_out_f,
            text="Remove Rule",
            fg_color="red",
            width=120,
            command=self.remove_outbound_rule,
        )

    def setup_rules_tab(self):
        self.tab_rules.grid_rowconfigure(0, weight=1)
        self.tab_rules.grid_columnconfigure(0, weight=1)
        f = ctk.CTkFrame(self.tab_rules)
        f.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(
            f, text="Global Access Rules", font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=10)
        self.txt_rules = ctk.CTkTextbox(f, font=("Consolas", 14))
        self.txt_rules.pack(fill="both", expand=True, padx=20, pady=10)
        btn_f = ctk.CTkFrame(f, fg_color="transparent")
        btn_f.pack(pady=10)
        ctk.CTkButton(
            btn_f,
            text="+ Create Custom Rule",
            fg_color="green",
            command=self.create_custom_rule,
        ).pack(side="left", padx=10)
        ctk.CTkButton(btn_f, text="Edit Rule (by ID)", command=self.edit_rule).pack(
            side="left", padx=10
        )
        ctk.CTkButton(
            btn_f,
            text="- Delete Rule (by ID)",
            fg_color="red",
            command=self.delete_rule,
        ).pack(side="left", padx=10)

    def setup_groups_tab(self):
        self.tab_groups.grid_rowconfigure(0, weight=1)
        self.tab_groups.grid_columnconfigure(0, weight=1)
        self.txt_groups = ctk.CTkTextbox(self.tab_groups, font=("Consolas", 14))
        self.txt_groups.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        btn_f = ctk.CTkFrame(self.tab_groups, fg_color="transparent")
        btn_f.grid(row=1, column=0, pady=10)
        ctk.CTkButton(btn_f, text="Add Group", command=self.add_group).pack(
            side="left", padx=5
        )
        ctk.CTkButton(btn_f, text="Rename Group", command=self.rename_group).pack(
            side="left", padx=5
        )
        ctk.CTkButton(
            btn_f, text="Delete Group", fg_color="red", command=self.delete_group
        ).pack(side="left", padx=5)
        ctk.CTkButton(btn_f, text="Add User", command=self.add_user_to_group).pack(
            side="left", padx=15
        )
        ctk.CTkButton(
            btn_f,
            text="Remove User",
            fg_color="red",
            command=self.remove_user_from_group,
        ).pack(side="left", padx=5)

    def setup_devices_tab(self):
        self.tab_devices.grid_rowconfigure(1, weight=1)
        self.tab_devices.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            self.tab_devices,
            text="Fetch Live Devices (CLI)",
            command=self.fetch_devices,
        ).grid(row=0, column=0, pady=10)
        self.txt_devices = ctk.CTkTextbox(self.tab_devices, font=("Consolas", 12))
        self.txt_devices.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

    def setup_raw_tab(self):
        self.tab_raw.grid_rowconfigure(0, weight=1)
        self.tab_raw.grid_columnconfigure(0, weight=1)
        self.txt_raw = ctk.CTkTextbox(self.tab_raw, font=("Consolas", 12))
        self.txt_raw.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        ctk.CTkButton(
            self.tab_raw, text="Apply Raw Changes", command=self.apply_raw
        ).grid(row=1, column=0, pady=5)

    def setup_topology_tab(self):
        self.tab_topology.grid_rowconfigure(0, weight=1)
        self.tab_topology.grid_columnconfigure(0, weight=1)
        self.topology_editor = TopologyEditor(
            self.tab_topology,
            self.acl_data,
            refresh_callback=self.on_topology_edited
        )
        self.topology_editor.grid(row=0, column=0, sticky="nsew")
        self.topology_editor.load_data(self.acl_data, self.current_filepath)

    def on_topology_edited(self):
        self.refresh_ui(refresh_topology=False)


    # ---- PARSERS ----
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

    # ---- LOGIC ----
    def refresh_ui(self, refresh_topology=True):
        for widget in self.tags_scrollable.winfo_children():
            widget.destroy()

        tags = self.get_all_tags()
        for t in tags:
            btn = ctk.CTkButton(
                self.tags_scrollable,
                text=t,
                anchor="w",
                fg_color="transparent",
                text_color=("black", "white"),
                command=lambda name=t: self.select_tag(name),
            )
            btn.pack(fill="x", pady=2)

        self.current_tag = None
        self.lbl_tag_title.configure(text="Select a tag")
        self.lbl_owners.configure(text="")
        self.txt_outbound.delete("0.0", "end")
        self.btn_rename_tag.pack_forget()
        self.btn_delete_tag.pack_forget()
        self.btn_add_owner.pack_forget()
        self.btn_remove_owner.pack_forget()
        self.btn_add_outbound.pack_forget()
        self.btn_remove_outbound.pack_forget()

        self.sort_rules()
        self.refresh_rules()
        self.refresh_groups()
        self.txt_raw.delete("0.0", "end")
        self.txt_raw.insert("0.0", json.dumps(self.acl_data, indent=4))

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

    def refresh_rules(self):
        self.txt_rules.delete("0.0", "end")
        for i, r in enumerate(self.acl_data.get("acls", [])):
            src = ", ".join(r.get("src", []))
            dst = ", ".join(r.get("dst", []))
            self.txt_rules.insert(
                "end", f"Rule ID {i}:\n  Source:      {src}\n  Destination: {dst}\n\n"
            )

    def refresh_groups(self):
        self.txt_groups.delete("0.0", "end")
        for g, users in self.acl_data.get("groups", {}).items():
            self.txt_groups.insert("end", f"{g}:\n")
            for u in users:
                self.txt_groups.insert("end", f"  - {u}\n")
            self.txt_groups.insert("end", "\n")

    # ---- TAG ACTIONS ----
    def select_tag(self, tag):
        self.current_tag = tag
        self.lbl_tag_title.configure(text=tag)
        owners = ", ".join(self.acl_data.get("tagOwners", {}).get(tag, []))
        self.lbl_owners.configure(text=owners)

        self.btn_rename_tag.pack(side="left", padx=5)
        self.btn_delete_tag.pack(side="left", padx=5)
        self.btn_add_owner.pack(side="left", padx=5)
        self.btn_remove_owner.pack(side="left", padx=5)
        self.btn_add_outbound.pack(side="left", padx=5)
        self.btn_remove_outbound.pack(side="left", padx=5)

        self.txt_outbound.delete("0.0", "end")
        outbound_rules = []
        for i, r in enumerate(self.acl_data.get("acls", [])):
            if tag in r.get("src", []):
                dst = ", ".join(r.get("dst", []))
                outbound_rules.append(f"Rule ID {i}: -> {dst}")

        if outbound_rules:
            self.txt_outbound.insert("end", "\n".join(outbound_rules))
        else:
            self.txt_outbound.insert("end", "No outbound rules.")

    def create_tag(self):
        d = ctk.CTkInputDialog(
            text="New tag name (we'll add 'tag:' for you):", title="New Tag"
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

        # 1. Rename in tagOwners
        owners = self.acl_data["tagOwners"].pop(old)
        self.acl_data["tagOwners"][new] = owners

        # 2. Rename in ACLs
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

        self.refresh_ui()
        self.select_tag(new)

    def delete_tag(self):
        if not self.current_tag:
            return
        t = self.current_tag
        if messagebox.askyesno(
            "Confirm", f"Permanently delete {t} and all associated rules?"
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
            self.refresh_ui()

    def add_owner(self):
        if not self.current_tag:
            return
        g = self.get_all_groups()
        d = CustomDialog(self, "Add Owner", ["Select Owner:"], [g], show_ports=False)
        self.wait_window(d)
        if d.result and d.result[0] not in self.acl_data["tagOwners"][self.current_tag]:
            self.acl_data["tagOwners"][self.current_tag].append(d.result[0])
            self.refresh_ui()
            self.select_tag(self.current_tag)

    def remove_owner(self):
        if not self.current_tag:
            return
        owners = self.acl_data["tagOwners"].get(self.current_tag, [])
        if not owners:
            return
        d = CustomDialog(
            self, "Remove Owner", ["Select Owner:"], [owners], show_ports=False
        )
        self.wait_window(d)
        if d.result:
            try:
                self.acl_data["tagOwners"][self.current_tag].remove(d.result[0])
                self.refresh_ui()
                self.select_tag(self.current_tag)
            except ValueError:
                pass

    def add_outbound_rule(self):
        if not self.current_tag:
            return
        opts = ["*"] + self.get_all_tags()
        d = CustomDialog(self, "Add Outbound", ["Dest:"], [opts])
        self.wait_window(d)
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

    def remove_outbound_rule(self):
        if not self.current_tag:
            return
        d = ctk.CTkInputDialog(text="Enter Rule ID to remove:", title="Remove Outbound")
        res = d.get_input()
        if res is not None:
            try:
                idx = int(res)
                r = self.acl_data.get("acls", [])[idx]
                if self.current_tag in r.get("src", []):
                    del self.acl_data["acls"][idx]
                    self.refresh_ui()
                    self.select_tag(self.current_tag)
                else:
                    messagebox.showerror(
                        "Error", "That rule does not belong to this tag."
                    )
            except:
                pass

    # ---- RULE ACTIONS ----
    def create_custom_rule(self):
        srcs = ["*"] + self.get_all_tags() + self.get_all_groups()
        dsts = ["*"] + self.get_all_tags()
        d = CustomDialog(self, "Custom Rule", ["Source:", "Dest:"], [srcs, dsts])
        self.wait_window(d)
        if d.result:
            s, dst, p = d.result
            self.acl_data.setdefault("acls", []).append(
                {"action": "accept", "src": [s], "dst": [f"{dst}:{p}"]}
            )
            self.refresh_ui()

    def edit_rule(self):
        d_id = ctk.CTkInputDialog(text="Enter Rule ID to edit:", title="Edit Rule")
        idx_str = d_id.get_input()
        if not idx_str:
            return
        try:
            idx = int(idx_str)
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
                f"Edit Rule {idx}",
                ["Source:", "Dest:"],
                [srcs, dsts],
                default_values=[old_src, old_dst, old_port],
            )
            self.wait_window(d)
            if d.result:
                s, dst, p = d.result
                r["src"] = [s]
                r["dst"] = [f"{dst}:{p}"]
                self.refresh_ui()
        except Exception as e:
            messagebox.showerror("Error", "Invalid Rule ID")

    def delete_rule(self):
        d = ctk.CTkInputDialog(text="Enter Rule ID:", title="Delete Rule")
        i = d.get_input()
        if i is not None:
            try:
                del self.acl_data["acls"][int(i)]
                self.refresh_ui()
            except:
                pass

    # ---- GROUP ACTIONS ----
    def add_group(self):
        d = ctk.CTkInputDialog(
            text="New Group Name (we'll add 'group:' for you):", title="Group"
        )
        g = d.get_input()
        if g:
            g = g.strip()
            if not g.startswith("group:"):
                g = f"group:{g}"
            self.acl_data.setdefault("groups", {})[g] = []
            self.refresh_ui()

    def rename_group(self):
        groups = list(self.acl_data.get("groups", {}).keys())
        if not groups:
            return
        d1 = CustomDialog(self, "Rename", ["Select Group:"], [groups], show_ports=False)
        self.wait_window(d1)
        if d1.result:
            old = d1.result[0]
            short_old = old.replace("group:", "")
            d2 = ctk.CTkInputDialog(text=f"Rename '{short_old}' to:", title="Rename")
            new = d2.get_input()
            if new:
                new = new.strip()
                if not new.startswith("group:"):
                    new = f"group:{new}"
                if new != old:
                    users = self.acl_data["groups"].pop(old)
                    self.acl_data["groups"][new] = users
                    for t, o_list in self.acl_data.get("tagOwners", {}).items():
                        if old in o_list:
                            self.acl_data["tagOwners"][t] = [
                                new if x == old else x for x in o_list
                            ]
                    for r in self.acl_data.get("acls", []):
                        if old in r.get("src", []):
                            r["src"] = [new if x == old else x for x in r["src"]]
                    self.refresh_ui()

    def delete_group(self):
        groups = list(self.acl_data.get("groups", {}).keys())
        if not groups:
            return
        d = CustomDialog(self, "Delete", ["Select Group:"], [groups], show_ports=False)
        self.wait_window(d)
        if d.result:
            g = d.result[0]
            if messagebox.askyesno("Confirm", f"Delete {g} and its rules?"):
                self.acl_data["groups"].pop(g, None)
                for t, o_list in self.acl_data.get("tagOwners", {}).items():
                    if g in o_list:
                        o_list.remove(g)
                self.acl_data["acls"] = [
                    r
                    for r in self.acl_data.get("acls", [])
                    if g not in r.get("src", [])
                ]
                self.refresh_ui()

    def add_user_to_group(self):
        groups = list(self.acl_data.get("groups", {}).keys())
        if not groups:
            return
        d = CustomDialog(
            self, "Add User", ["Select Group:"], [groups], show_ports=False
        )
        self.wait_window(d)
        if d.result:
            g = d.result[0]
            u = ctk.CTkInputDialog(text=f"Email for {g}:", title="User").get_input()
            if u:
                self.acl_data["groups"][g].append(u.strip())
                self.refresh_ui()

    def remove_user_from_group(self):
        groups = list(self.acl_data.get("groups", {}).keys())
        if not groups:
            return
        d = CustomDialog(
            self, "Select Group", ["Select Group:"], [groups], show_ports=False
        )
        self.wait_window(d)
        if d.result:
            g = d.result[0]
            users = self.acl_data["groups"].get(g, [])
            if not users:
                return
            d2 = CustomDialog(
                self, "Remove User", ["Select User:"], [users], show_ports=False
            )
            self.wait_window(d2)
            if d2.result:
                self.acl_data["groups"][g].remove(d2.result[0])
                self.refresh_ui()

    # ---- DEVICES ----
    def fetch_devices(self):
        self.txt_devices.delete("0.0", "end")
        self.txt_devices.insert("end", "Fetching live devices...\n\n")
        self.update()
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                peers = data.get("Peer", {})
                self.txt_devices.insert(
                    "end",
                    f"{'Hostname':<25} | {'IP Address':<15} | {'OS':<10} | {'Tags'}\n",
                )
                self.txt_devices.insert("end", "-" * 80 + "\n")
                self_node = data.get("Self", {})
                self._print_device(self_node, "Self")
                for k, v in peers.items():
                    self._print_device(v)
        except Exception as e:
            self.txt_devices.insert("end", f"Error: {e}")

    def _print_device(self, node, label=""):
        host = (
            f"{node.get('HostName', 'Unknown')} ({label})"
            if label
            else node.get("HostName", "Unknown")
        )
        ips = node.get("TailscaleIPs", [""])
        self.txt_devices.insert(
            "end",
            f"{host:<25} | {ips[0] if ips else '':<15} | {node.get('OS', ''):<10} | {', '.join(node.get('Tags', []))}\n",
        )

    # ---- IO ----
    def apply_raw(self):
        try:
            self.acl_data = json5.loads(self.txt_raw.get("0.0", "end"))
            self.refresh_ui()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_json(self):
        p = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if p:
            self.current_filepath = p
            with open(p, "r", encoding="utf-8") as f:
                self.acl_data = json5.loads(f.read())
            self.lbl_status.configure(text=f"Loaded: {p}")
            
            # Save last config path
            try:
                import os
                state_file = os.path.join(os.path.dirname(__file__), ".last_config.txt")
                with open(state_file, "w", encoding="utf-8") as f:
                    f.write(p)
            except Exception:
                pass
                
            self.refresh_ui()

    def save_json(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON Files", "*.json")]
        )
        if p:
            self.current_filepath = p
            self.apply_raw()
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.acl_data, f, indent=4)
            self.lbl_status.configure(text=f"Saved: {p}")
            
            # Save last config path
            try:
                import os
                state_file = os.path.join(os.path.dirname(__file__), ".last_config.txt")
                with open(state_file, "w", encoding="utf-8") as f:
                    f.write(p)
            except Exception:
                pass
                
            messagebox.showinfo("Success", "Saved successfully!")

    def autoload_last_config(self):
        try:
            import os
            state_file = os.path.join(os.path.dirname(__file__), ".last_config.txt")
            if os.path.exists(state_file):
                with open(state_file, "r", encoding="utf-8") as f:
                    p = f.read().strip()
                if p and os.path.exists(p):
                    self.current_filepath = p
                    with open(p, "r", encoding="utf-8") as f:
                        self.acl_data = json5.loads(f.read())
                    self.lbl_status.configure(text=f"Autoloaded: {p}")
                    self.refresh_ui()
        except Exception as e:
            print(f"Error autoloading last config: {e}")


if __name__ == "__main__":
    app = ACLManagerV5()
    app.mainloop()
