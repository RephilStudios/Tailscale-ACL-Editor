# Tailscale ACL Manager & Topology Editor

A modern, interactive, and beautiful desktop application to visualize, design, and manage Tailscale Access Control Lists (ACLs) and network topologies in real-time. Built with Python and CustomTkinter.

---

## Key Features

- **Interactive Topology Graph Editor**: Drag-and-drop nodes, zoom controls (0.5x to 1.5x, with mouse-wheel zoom support), grid alignment, and visual highlights.
- **Bidirectional Editing**: Modifying nodes, edges, or ACL connections dynamically updates the underlying JSON configuration, and editing the raw JSON immediately refreshes the topology layout.
- **Clean Access Rules & Port Badges**: Beautiful green ACL links, complete with port labels (e.g. `:80,443`), point from sources to destinations.
- **Automatic Same-Column Loops**: Links between same-column nodes (such as client-to-server tag rules) automatically route as clean right-side arcs to remain fully visible.
- **Groups & Memberships**: Manage autogroups, custom groups, and user memberships visually.
- **Smart Position Persistence**: Dragged node positions are automatically cached in memory and saved to `<filename>.positions.json` so your customized layouts are preserved across restarts and visibility toggles.
- **Auto-load Session History**: Automatically saves the path of the last used configuration file in `.last_config.txt` and loads it on startup.
- **Dark Mode Aesthetic**: A sleek, premium UI built around HSL slate-900 palettes.

---

## Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repository-url>
   cd tailscale-acl-manager
   ```

2. **Set up a virtual environment (optional but recommended)**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## Usage

Start the application by running the main entry point:

```bash
python acl_manager.py
```

### Tips for the Topology Editor:
- **Navigation**: Use the mouse wheel to zoom in and out. Click and drag on empty canvas space to scroll the workspace.
- **Drawing Connections**: Click and drag from any output pin (green circle on the right side of a node) to any input pin (green circle on the left side of a node) to establish a relationship.
- **Interactive Prompts**: Dragging a connection to a tag will present a custom prompt allowing you to define it as either an **Access Rule** or **Tag Owner**.

---

## Project Structure

- `acl_manager.py`: Main application UI coordinating the tabs (Access Rules Builder, Groups Manager, Raw JSON Editor, and Topology Editor).
- `topology_editor.py`: Interactive graph engine containing canvas rendering, S-curve Bezier calculations, event handlers, and CustomTkinter dialog components.
- `requirements.txt`: Python package requirements.
- `.gitignore`: Excludes Python byte caches, local environment folders, and session-specific states.
- `LICENSE`: The open-source MIT License.

---

## License

This project is licensed under the [MIT License](LICENSE).
