"""NiceGUI web interface for ArduCLI."""

import asyncio
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from nicegui import ui

from models import ConnectionConfig
from services import MAVLinkService, ParameterMetadataService, ParamMeta


class WebInterface:
    _RECENT_CONNS_FILE = Path.home() / ".arducli" / "recent_connections.json"
    _MAX_RECENT = 10

    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.service = MAVLinkService(config)
        self._meta_service = ParameterMetadataService()
        self._recent_conns: list[str] = self._load_recent_conns()
        self._param_rows: list = []
        self._recently_accessed: OrderedDict = OrderedDict()
        self._recently_modified: OrderedDict = OrderedDict()
        self._selected_param: Optional[str] = None
        self._selected_meta: Optional[ParamMeta] = None
        self._seen_message_count: int = 0
        self._filter_text: str = ""
        self._connecting: bool = False
        self._loading_params: bool = False
        self._reboot_needed: bool = False
        self._raw_filter: str = ""
        self._raw_prev: dict = {}  # {type.field: last_seen_value}
        self._raw_changed: dict = {}  # {type.field: changed_at timestamp}
        # UI refs
        self._status_label = None
        self._param_table = None
        self._edit_name = None
        self._edit_value = None
        self._detail_col = None  # dynamic description/range/bitmask/enum section
        self._recent_accessed_col = None
        self._recent_modified_col = None
        self._connect_btn = None
        self._conn_input = None
        self._reboot_btn = None
        self._raw_table = None
        self._arm_btn = None
        self._mode_btn = None
        self._message_log = None
        self._params_msg_log = None
        self._telemetry = {}
        self._statusbar = {}

    def _load_recent_conns(self) -> list[str]:
        try:
            return json.loads(self._RECENT_CONNS_FILE.read_text())
        except Exception:
            return []

    def _save_recent_conn(self, conn_str: str):
        if not conn_str:
            return
        conns = [c for c in self._recent_conns if c != conn_str]
        conns.insert(0, conn_str)
        self._recent_conns = conns[: self._MAX_RECENT]
        try:
            self._RECENT_CONNS_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._RECENT_CONNS_FILE.write_text(json.dumps(self._recent_conns))
        except Exception:
            pass

    def register_routes(self):
        """Register @ui.page routes. Must be called at module import time for reload to work."""

        @ui.page("/")
        async def index():
            await self._build_page()

    def run(self, host: str = "127.0.0.1", port: int = 8080, reload: bool = False):
        ui.run(host=host, port=port, title="ArduCLI", reload=reload, show=True, storage_secret="arducli-local")

    # ── Page layout ───────────────────────────────────────────────────────────

    async def _build_page(self):
        # Connection bar
        with ui.header().classes("bg-gray-900 text-white items-center gap-3 px-4 py-2"):
            ui.label("ArduCLI").classes("text-lg font-bold font-mono")
            self._status_label = ui.label("● Not connected").classes("text-red-400 text-sm font-mono")
            ui.space()
            self._conn_input = (
                ui.input(
                    placeholder="Connection string  (blank = auto-serial,  udpin:0.0.0.0:14550,  tcp:192.168.1.5:5760)"
                )
                .classes("font-mono text-sm")
                .props("dense outlined dark")
                .style("min-width: 420px")
            )
            with ui.element("div"):
                ui.button("▾", on_click=lambda: recent_menu.open()).props("dense flat color=grey-5").classes(
                    "font-mono"
                )
                with ui.menu() as recent_menu:
                    if self._recent_conns:
                        for cs in self._recent_conns:
                            ui.menu_item(cs, on_click=lambda c=cs: setattr(self._conn_input, "value", c)).classes(
                                "font-mono text-sm"
                            )
                    else:
                        ui.menu_item("No recent connections").props("disabled")
            self._connect_btn = ui.button("Connect", on_click=self._toggle_connection).props("color=primary dense")
            ui.button("Load Params", on_click=self._load_parameters).props("color=secondary dense")
            self._reboot_btn = ui.button("Reboot FC", on_click=self._confirm_reboot).props(
                "color=warning dense outline"
            )

        # Always-visible status strip
        sb = self._statusbar
        with ui.row().classes("w-full items-center gap-4 px-4 py-1 bg-gray-800").style(
            "border-bottom: 1px solid #374151;"
        ):
            sb["armed"] = ui.label("DISARMED").classes("font-mono text-sm font-bold text-green-400")
            self._arm_btn = (
                ui.button("Arm", on_click=self._confirm_arm_disarm)
                .props("dense flat no-caps size=sm color=green-4")
                .classes("font-mono")
            )
            ui.label("|").classes("text-gray-600")
            with ui.row().classes("items-center gap-1"):
                ui.label("Mode:").classes("text-gray-400 text-xs font-mono")
                sb["mode"] = ui.label("—").classes("font-mono text-sm text-white")
            self._mode_btn = (
                ui.button("⟳", on_click=self._show_mode_picker)
                .props("dense flat size=sm color=blue-4")
                .classes("font-mono")
            )
            ui.label("|").classes("text-gray-600")
            with ui.row().classes("items-center gap-1"):
                ui.label("HDG:").classes("text-gray-400 text-xs font-mono")
                sb["heading"] = ui.label("—").classes("font-mono text-sm text-white")
            with ui.row().classes("items-center gap-1"):
                ui.label("Roll:").classes("text-gray-400 text-xs font-mono")
                sb["roll"] = ui.label("—").classes("font-mono text-sm text-white")
            with ui.row().classes("items-center gap-1"):
                ui.label("Pitch:").classes("text-gray-400 text-xs font-mono")
                sb["pitch"] = ui.label("—").classes("font-mono text-sm text-white")

        # Tabs
        with ui.tabs().classes("w-full bg-gray-800 text-white") as tabs:
            t_params = ui.tab("Parameters", icon="tune")
            t_status = ui.tab("Status", icon="speed")
            t_messages = ui.tab("Messages", icon="message")
            t_raw = ui.tab("Raw MAVLink", icon="data_object")

        with ui.tab_panels(tabs, value=t_params).classes("w-full bg-gray-900").style("flex: 1; overflow: hidden;"):
            with ui.tab_panel(t_params).classes("p-2"):
                self._build_params_panel()
            with ui.tab_panel(t_status).classes("p-4"):
                self._build_status_panel()
            with ui.tab_panel(t_messages).classes("p-2"):
                self._build_messages_panel()
            with ui.tab_panel(t_raw).classes("p-2"):
                self._build_raw_panel()

        ui.timer(0.5, self._tick_telemetry)
        ui.timer(1.0, self._tick_messages)
        ui.timer(1.0, self._tick_raw)

    # ── Parameters panel ──────────────────────────────────────────────────────

    def _build_params_panel(self):
        with ui.row().classes("w-full items-center gap-2 mb-2"):
            ui.input("Filter / regex", on_change=lambda e: self._on_filter_change(e.value)).classes("font-mono").props(
                "clearable dense outlined dark"
            ).style("min-width: 320px")

        with ui.row().classes("w-full gap-3").style("height: calc(100vh - 200px)"):
            # Left: messages sidebar
            with ui.column().classes("gap-1").style("width: 260px; flex-shrink: 0;"):
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label("Messages").classes("text-xs font-bold text-gray-400 uppercase")
                    ui.button("Clear", on_click=self._clear_params_messages).props("flat dense size=xs color=grey")
                self._params_msg_log = (
                    ui.log(max_lines=200)
                    .classes("w-full font-mono")
                    .style(
                        "height: calc(100vh - 235px); font-size: 11px; "
                        "background: #0d0d1a; color: #b0b0b0; border-radius: 4px;"
                    )
                )

            # Centre: parameter table
            cols = [
                {
                    "name": "name",
                    "label": "Parameter",
                    "field": "name",
                    "sortable": True,
                    "align": "left",
                    "style": "width: 160px",
                },
                {
                    "name": "value",
                    "label": "Value",
                    "field": "value",
                    "sortable": True,
                    "align": "right",
                    "style": "width: 90px",
                },
                {
                    "name": "units",
                    "label": "Units",
                    "field": "units",
                    "sortable": False,
                    "align": "left",
                    "style": "width: 60px",
                },
                {
                    "name": "display_name",
                    "label": "Description",
                    "field": "display_name",
                    "sortable": True,
                    "align": "left",
                },
            ]
            self._param_table = (
                ui.table(columns=cols, rows=[], row_key="name", on_select=self._on_select)
                .classes("flex-grow font-mono text-sm")
                .props("selection=single dense dark virtual-scroll")
                .style("height: 100%; min-width: 0; overflow-y: auto;")
            )
            self._param_table.on("row-click", self._on_row_click)

            # Right: detail + edit + recents sidebar
            with ui.column().classes("gap-3").style("width: 300px; flex-shrink: 0; overflow-y: auto; height: 100%;"):
                # Edit card
                with ui.card().classes("bg-gray-800 text-white w-full"):
                    ui.label("Edit").classes("text-xs font-bold text-gray-400 uppercase")
                    self._edit_name = ui.label("—").classes("font-mono font-bold text-yellow-300 text-sm")
                    self._edit_value = ui.input("Value").classes("w-full font-mono").props("dense outlined dark")
                    ui.button("Set", on_click=self._do_set).props("color=warning dense")

                # Dynamic detail section (description, range, bitmask, enum)
                self._detail_col = ui.column().classes("w-full gap-2")

                # Recently accessed
                with ui.card().classes("bg-gray-800 text-white w-full"):
                    ui.label("Recently Accessed").classes("text-xs font-bold text-gray-400 uppercase mb-1")
                    self._recent_accessed_col = ui.column().classes("w-full gap-0")

                # Recently modified
                with ui.card().classes("bg-gray-800 text-white w-full"):
                    ui.label("Recently Modified").classes("text-xs font-bold text-gray-400 uppercase mb-1")
                    self._recent_modified_col = ui.column().classes("w-full gap-0")

    # ── Status panel ──────────────────────────────────────────────────────────

    def _build_status_panel(self):
        t = self._telemetry
        card = "bg-gray-800 text-white"
        lbl = "font-mono text-sm"

        def hdr(text, color):
            ui.label(text).classes(f"font-bold {color} mb-1 text-xs uppercase tracking-wide")

        with ui.grid(columns=3).classes("w-full gap-3"):
            # ── GPS ──────────────────────────────────────────────────────────
            with ui.card().classes(card):
                hdr("GPS", "text-blue-300")
                t["gps_status"] = ui.label("Status: —").classes(lbl)
                t["gps_lat"] = ui.label("Lat:  —").classes(lbl)
                t["gps_lon"] = ui.label("Lon:  —").classes(lbl)
                t["gps_alt"] = ui.label("Alt (MSL): —").classes(lbl)
                t["rel_alt"] = ui.label("Alt (Rel): —").classes(lbl)
                t["gps_hdop"] = ui.label("HDOP: —").classes(lbl)
                t["gps_vdop"] = ui.label("VDOP: —").classes(lbl)

            # ── Battery ───────────────────────────────────────────────────────
            with ui.card().classes(card):
                hdr("Battery", "text-green-300")
                t["bat_v"] = ui.label("Voltage:   —").classes(lbl)
                t["bat_a"] = ui.label("Current:   —").classes(lbl)
                t["bat_pct"] = ui.label("Remaining: —").classes(lbl)

            # ── System ────────────────────────────────────────────────────────
            with ui.card().classes(card):
                hdr("System", "text-orange-300")
                t["armed"] = ui.label("State: DISARMED").classes(f"{lbl} text-green-400")
                t["mode"] = ui.label("Mode: —").classes(lbl)
                t["throttle"] = ui.label("Throttle: —").classes(lbl)

            # ── Speed & Altitude ──────────────────────────────────────────────
            with ui.card().classes(card):
                hdr("Speed & Altitude", "text-cyan-300")
                t["airspeed"] = ui.label("Airspeed:   —").classes(lbl)
                t["groundspeed"] = ui.label("Groundspeed:—").classes(lbl)
                t["climb_rate"] = ui.label("Climb rate: —").classes(lbl)
                t["alt_vfr"] = ui.label("Alt (baro): —").classes(lbl)

            # ── Attitude ──────────────────────────────────────────────────────
            with ui.card().classes(card):
                hdr("Attitude", "text-purple-300")
                t["heading"] = ui.label("Heading:  —").classes(lbl)
                t["roll"] = ui.label("Roll:     —").classes(lbl)
                t["pitch"] = ui.label("Pitch:    —").classes(lbl)
                t["yaw_rate"] = ui.label("Yaw rate: —").classes(lbl)
                t["wind"] = ui.label("Wind:     —").classes(lbl)

            # ── EKF ───────────────────────────────────────────────────────────
            with ui.card().classes(card):
                hdr("EKF", "text-yellow-300")
                t["ekf_ok"] = ui.label("Status: —").classes(lbl)
                t["ekf_vel"] = ui.label("Vel var:      —").classes(lbl)
                t["ekf_pos_h"] = ui.label("Pos horiz:    —").classes(lbl)
                t["ekf_pos_v"] = ui.label("Pos vert:     —").classes(lbl)
                t["ekf_compass"] = ui.label("Compass var:  —").classes(lbl)
                t["ekf_terrain"] = ui.label("Terrain var:  —").classes(lbl)

            # ── Vibration ─────────────────────────────────────────────────────
            with ui.card().classes(card):
                hdr("Vibration", "text-red-300")
                t["vib_x"] = ui.label("X: —").classes(lbl)
                t["vib_y"] = ui.label("Y: —").classes(lbl)
                t["vib_z"] = ui.label("Z: —").classes(lbl)
                t["vib_clip"] = ui.label("Clipping: —").classes(lbl)

            # ── RC / Link ─────────────────────────────────────────────────────
            with ui.card().classes(card):
                hdr("RC / Link", "text-pink-300")
                t["rssi"] = ui.label("RSSI: —").classes(lbl)

            # ── Compass ───────────────────────────────────────────────────────
            with ui.card().classes(card):
                hdr("Compass", "text-indigo-300")
                t["mag_field"] = ui.label("Field strength: —").classes(lbl)

    # ── Raw MAVLink panel ─────────────────────────────────────────────────────

    def _build_raw_panel(self):
        with ui.row().classes("w-full items-center gap-2 mb-2"):
            ui.input(
                "Filter  (type name, field name, or value — regex ok)",
                on_change=lambda e: self._on_raw_filter_change(e.value),
            ).classes("flex-grow font-mono").props("clearable dense outlined dark")
            self._raw_msg_count = ui.label("").classes("text-gray-400 text-xs font-mono")

        cols = [
            {
                "name": "type",
                "label": "Message Type",
                "field": "type",
                "sortable": True,
                "align": "left",
                "style": "width: 200px; font-weight: bold;",
            },
            {
                "name": "field",
                "label": "Field",
                "field": "field",
                "sortable": True,
                "align": "left",
                "style": "width: 200px;",
            },
            {"name": "value", "label": "Value", "field": "value", "sortable": False, "align": "left"},
            {
                "name": "age",
                "label": "Age",
                "field": "age",
                "sortable": True,
                "align": "right",
                "style": "width: 80px;",
            },
        ]
        self._raw_table = (
            ui.table(columns=cols, rows=[], row_key="key")
            .classes("w-full font-mono text-sm")
            .props("dense dark virtual-scroll")
            .style("height: calc(100vh - 175px);")
        )

    def _on_raw_filter_change(self, value: str):
        self._raw_filter = value or ""

    # ── Messages panel ────────────────────────────────────────────────────────

    def _build_messages_panel(self):
        with ui.row().classes("items-center gap-2 mb-1"):
            ui.label("FC Messages (STATUSTEXT)").classes("text-gray-300 text-sm")
            ui.button("Clear", on_click=self._clear_messages).props("flat dense size=sm color=grey")
        self._message_log = (
            ui.log(max_lines=500)
            .classes("w-full font-mono text-sm")
            .style("height: calc(100vh - 150px); background: #0d0d1a; color: #d0d0d0;")
        )

    # ── Detail panel (dynamic, rebuilt on param select) ───────────────────────

    def _rebuild_detail(self, meta: Optional[ParamMeta], current_value: str):
        self._detail_col.clear()
        if not meta:
            return

        with self._detail_col:
            # Display name + description
            if meta.display_name:
                ui.label(meta.display_name).classes("text-sm font-bold text-gray-200 font-mono")
            if meta.description:
                with ui.card().classes("bg-gray-900 w-full"):
                    ui.label(meta.description).classes("text-xs text-gray-300").style(
                        "white-space: pre-wrap; word-break: break-word;"
                    )

            # Range / units / badges row
            badges = []
            if meta.range_min is not None:
                range_str = f"{meta.range_min:.6g} – {meta.range_max:.6g}"
                if meta.units:
                    range_str += f"  {meta.units}"
                badges.append(("range", range_str, "blue-gray"))
            if meta.increment is not None:
                badges.append(("step", f"step {meta.increment:.6g}", "blue-gray"))
            if meta.reboot_required:
                badges.append(("reboot", "Reboot required", "orange"))
            if meta.read_only:
                badges.append(("ro", "Read-only", "grey"))
            if meta.user_level:
                badges.append(("level", meta.user_level, "blue-gray"))

            if badges:
                with ui.row().classes("flex-wrap gap-1"):
                    for _, label_text, color in badges:
                        ui.badge(label_text, color=color).classes("text-xs font-mono")

            # Bitmask editor
            if meta.bitmask:
                with ui.card().classes("bg-gray-900 w-full"):
                    ui.label("Bitmask").classes("text-xs font-bold text-gray-400 uppercase mb-1")
                    try:
                        cur_int = int(float(current_value or "0"))
                    except ValueError:
                        cur_int = 0
                    for bit_str, bit_name in sorted(meta.bitmask.items(), key=lambda x: int(x[0])):
                        bit = int(bit_str)
                        checked = bool(cur_int & (1 << bit))
                        cb = ui.checkbox(f"{bit_name}", value=checked).classes("text-xs text-gray-300")
                        cb.on_value_change(lambda e, b=bit: self._toggle_bit(b, e.value))

            # Enum picker
            if meta.values:
                with ui.card().classes("bg-gray-900 w-full"):
                    ui.label("Options").classes("text-xs font-bold text-gray-400 uppercase mb-1")
                    for val_str, val_name in sorted(meta.values.items(), key=lambda x: float(x[0])):
                        ui.button(
                            f"{val_str}  {val_name}",
                            on_click=lambda v=val_str: self._pick_enum(v),
                        ).props("flat dense align=left").classes("w-full text-xs font-mono text-gray-300 text-left")

    def _toggle_bit(self, bit: int, checked: bool):
        try:
            current = int(float(self._edit_value.value or "0"))
        except ValueError:
            current = 0
        current = (current | (1 << bit)) if checked else (current & ~(1 << bit))
        self._edit_value.value = str(current)

    def _pick_enum(self, value: str):
        self._edit_value.value = value

    # ── Button / event handlers ───────────────────────────────────────────────

    async def _toggle_connection(self):
        if self.service.is_connected():
            await self._do_disconnect()
        else:
            await self._do_connect(self._conn_input.value if self._conn_input else "")

    def _set_connect_btn_state(self, connected: bool):
        if not self._connect_btn:
            return
        if connected:
            self._connect_btn._props["label"] = "Disconnect"
            self._connect_btn._props["color"] = "negative"
        else:
            self._connect_btn._props["label"] = "Connect"
            self._connect_btn._props["color"] = "primary"
        self._connect_btn.props(remove="loading")
        self._connect_btn.update()

    async def _do_connect(self, conn_str: str):
        if self._connecting:
            return
        self._connecting = True
        if self._connect_btn:
            self._connect_btn.props("loading")
        conn_str = conn_str.strip()
        ui.notify("Connecting…", type="info", timeout=2000)

        ok = await asyncio.to_thread(self.service.connect, port=conn_str or None)
        self._connecting = False
        if ok:
            if conn_str:
                self._save_recent_conn(conn_str)
            self._set_connect_btn_state(True)
            self._status_label.set_text("● Connected")
            self._status_label.update()
            self._status_label.classes("text-green-400", remove="text-red-400")
            ui.notify("Connected", type="positive")
            try:
                await asyncio.to_thread(self.service.start_telemetry)
            except Exception:
                pass
            await self._load_parameters()
        else:
            self._set_connect_btn_state(False)
            self._status_label.set_text("● Not connected")
            self._status_label.update()
            self._status_label.classes("text-red-400", remove="text-green-400")
            ui.notify("Connection failed", type="negative")

    async def _do_disconnect(self):
        self.service.disconnect()
        self._set_connect_btn_state(False)
        self._status_label.set_text("● Not connected")
        self._status_label.update()
        self._status_label.classes("text-red-400", remove="text-green-400")
        ui.notify("Disconnected", type="warning")

    async def _load_parameters(self):
        if not self.service.is_connected():
            ui.notify("Not connected", type="negative")
            return
        if self._loading_params:
            return
        self._loading_params = True
        ui.notify("Loading parameters…", type="info")

        # Load metadata in background if not yet loaded (fire-and-forget)
        if not self._meta_service.is_loaded():
            device_info = self.service.get_device_info()
            if device_info:
                asyncio.ensure_future(
                    asyncio.to_thread(
                        self._meta_service.load,
                        device_info.vehicle_type,
                        device_info.firmware_version or "",
                    )
                )

        try:
            params = await asyncio.to_thread(self.service.load_parameters, None)
            self._rebuild_param_rows(params)
            self._param_table.rows = self._param_rows.copy()
            self._param_table.update()
            ui.notify(f"Loaded {len(params)} parameters", type="positive")
            # Drain accumulated messages into _raw now that the serial port is free again.
            await asyncio.to_thread(self._drain_telemetry)
        except Exception as e:
            self._mark_disconnected(str(e))
        finally:
            self._loading_params = False

    def _rebuild_param_rows(self, params: dict):
        """Build _param_rows, enriching with metadata if available."""
        rows = []
        for k, v in sorted(params.items()):
            meta = self._meta_service.get(k) if self._meta_service.is_loaded() else None
            rows.append(
                {
                    "name": k,
                    "value": f"{v:.6g}",
                    "units": meta.units if meta else "",
                    "display_name": meta.display_name if meta else "",
                }
            )
        self._param_rows = rows

    def _on_filter_change(self, value: str):
        self._filter_text = value or ""
        self._filter(self._filter_text)

    def _filter(self, query: str):
        query = (query or "").strip().upper()
        if not query:
            self._param_table.rows = self._param_rows.copy()
        else:
            try:
                pat = re.compile(query)
                rows = [r for r in self._param_rows if pat.match(r["name"])]
            except re.error:
                rows = [r for r in self._param_rows if query in r["name"]]
            self._param_table.rows = rows
        self._param_table.update()

    def _on_row_click(self, e):
        # Quasar row-click args: [event, row, index]
        if not e.args or len(e.args) < 2:
            return
        row = e.args[1]
        if not isinstance(row, dict):
            return
        # Drive the visual checkbox selection, then process
        self._param_table.selected = [row]
        self._param_table.update()
        self._process_selection(row)

    def _on_select(self, e):
        if not e.selection:
            return
        self._process_selection(e.selection[0])

    def _process_selection(self, row: dict):
        name = row["name"]
        self._selected_param = name
        self._selected_meta = self._meta_service.get(name) if self._meta_service.is_loaded() else None

        self._edit_name.set_text(name)
        self._edit_name.update()
        self._edit_value.value = row["value"]

        self._rebuild_detail(self._selected_meta, row["value"])

        self._recently_accessed.pop(name, None)
        self._recently_accessed[name] = row["value"]
        while len(self._recently_accessed) > 8:
            self._recently_accessed.popitem(last=False)
        self._redraw_recent(self._recent_accessed_col, self._recently_accessed, modified=False)

    async def _do_set(self):
        if not self._selected_param:
            ui.notify("Select a parameter first", type="warning")
            return
        if not self.service.is_connected():
            ui.notify("Not connected", type="negative")
            return
        try:
            new_val = float(self._edit_value.value)
        except ValueError:
            ui.notify("Value must be a number", type="negative")
            return

        old_val = self.service.get_parameter(self._selected_param)
        ok = await asyncio.to_thread(self.service.set_parameter, self._selected_param, new_val)
        if ok:
            val_str = f"{new_val:.6g}"
            for i, row in enumerate(self._param_rows):
                if row["name"] == self._selected_param:
                    self._param_rows[i] = {**row, "value": val_str}
                    break
            self._filter(self._filter_text)  # reassigns rows + calls update()

            old_str = f"{old_val:.6g}" if old_val is not None else "?"
            self._recently_modified.pop(self._selected_param, None)
            self._recently_modified[self._selected_param] = (old_str, val_str)
            while len(self._recently_modified) > 8:
                self._recently_modified.popitem(last=False)
            self._redraw_recent(self._recent_modified_col, self._recently_modified, modified=True)

            if self._selected_meta and self._selected_meta.reboot_required:
                self._reboot_needed = True
                if self._reboot_btn:
                    self._reboot_btn.props("color=negative")
                    self._reboot_btn.props(remove="outline")
                    self._reboot_btn.update()
                ui.notify(
                    f"{self._selected_param} = {new_val}  —  reboot required",
                    type="warning",
                    timeout=5000,
                )
            else:
                ui.notify(f"{self._selected_param} = {new_val}", type="positive")
        else:
            ui.notify("Failed to set parameter", type="negative")

    def _redraw_recent(self, container, data: OrderedDict, modified: bool):
        container.clear()
        for name, val in reversed(list(data.items())):
            with container:
                if modified:
                    old, new = val
                    ui.label(name).classes("font-mono text-xs text-yellow-300")
                    ui.label(f"  {old} → {new}").classes("font-mono text-xs text-gray-400")
                else:
                    ui.label(f"{name}  {val}").classes("font-mono text-xs text-gray-300")

    async def _confirm_arm_disarm(self):
        if not self.service.is_connected():
            ui.notify("Not connected", type="negative")
            return
        armed = self.service.get_telemetry().armed
        if armed:
            with ui.dialog() as dlg, ui.card().classes("bg-gray-800 text-white"):
                ui.label("Disarm?").classes("text-lg font-bold mb-2")
                ui.label("The vehicle will disarm immediately.").classes("text-gray-300 text-sm mb-4")
                with ui.row().classes("gap-2 justify-end w-full"):
                    ui.button("Cancel", on_click=dlg.close).props("flat color=grey")
                    ui.button("Disarm", on_click=lambda: self._do_disarm(dlg)).props("color=negative")
            dlg.open()
        else:
            with ui.dialog() as dlg, ui.card().classes("bg-gray-800 text-white"):
                ui.label("Arm vehicle?").classes("text-lg font-bold mb-2 text-red-400")
                ui.label("⚠  Ensure props are removed or area is clear.").classes(
                    "text-yellow-300 text-sm font-bold mb-4"
                )
                with ui.row().classes("gap-2 justify-end w-full"):
                    ui.button("Cancel", on_click=dlg.close).props("flat color=grey")
                    ui.button("Arm", on_click=lambda: self._do_arm(dlg)).props("color=warning")
            dlg.open()

    async def _do_arm(self, dialog):
        dialog.close()
        ok = await asyncio.to_thread(self.service.arm)
        if ok:
            ui.notify("Arm command sent", type="positive")
        else:
            ui.notify("Failed to send arm command", type="negative")

    async def _do_disarm(self, dialog):
        dialog.close()
        ok = await asyncio.to_thread(self.service.disarm)
        if ok:
            ui.notify("Disarm command sent", type="positive")
        else:
            ui.notify("Failed to send disarm command", type="negative")

    async def _show_mode_picker(self):
        if not self.service.is_connected():
            ui.notify("Not connected", type="negative")
            return
        modes = self.service.get_available_modes()
        if not modes:
            ui.notify("No mode list available for this vehicle type", type="warning")
            return
        current = self.service.get_telemetry().mode

        with ui.dialog() as dlg, ui.card().classes("bg-gray-800 text-white").style("min-width: 260px"):
            ui.label("Set Flight Mode").classes("text-lg font-bold mb-2")
            with ui.column().classes("w-full gap-1"):
                for num, name in sorted(modes.items(), key=lambda x: x[1]):
                    is_current = name == current
                    (
                        ui.button(
                            f"{'● ' if is_current else '  '}{name}",
                            on_click=lambda n=num, nm=name, d=dlg: self._do_set_mode(n, nm, d),
                        )
                        .props("flat dense no-caps align=left")
                        .classes("w-full font-mono text-sm " + ("text-yellow-300" if is_current else "text-gray-300"))
                    )
        dlg.open()

    async def _do_set_mode(self, mode_number: int, mode_name: str, dialog):
        dialog.close()
        ok = await asyncio.to_thread(self.service.set_mode, mode_number)
        if ok:
            ui.notify(f"Mode → {mode_name}", type="positive")
        else:
            ui.notify("Failed to set mode", type="negative")

    async def _confirm_reboot(self):
        if not self.service.is_connected():
            ui.notify("Not connected", type="negative")
            return
        with ui.dialog() as dialog, ui.card().classes("bg-gray-800 text-white"):
            ui.label("Reboot Flight Controller?").classes("text-lg font-bold mb-2")
            ui.label("This will restart the FC. Any unsaved configuration will be lost.").classes(
                "text-gray-300 text-sm mb-4"
            )
            with ui.row().classes("gap-2 justify-end w-full"):
                ui.button("Cancel", on_click=dialog.close).props("flat color=grey")
                ui.button("Reboot", on_click=lambda: self._do_reboot(dialog)).props("color=warning")
        dialog.open()

    async def _do_reboot(self, dialog):
        dialog.close()
        ok = await asyncio.to_thread(self.service.reboot)
        if ok:
            self._reboot_needed = False
            if self._reboot_btn:
                self._reboot_btn.props(remove="color=negative")
                self._reboot_btn.props("color=warning outline")
                self._reboot_btn.update()
            ui.notify("Reboot command sent — waiting for FC to restart…", type="positive", timeout=8000)
            # Give the FC time to shut down and reboot, then re-request telemetry streams.
            # The serial connection usually survives the cycle; the FC just resets its MAVLink state.
            await asyncio.sleep(6)
            if self.service.is_connected():
                self.service.telemetry_service._stream_requested = False
                await asyncio.to_thread(self.service.start_telemetry)
                ui.notify("Telemetry streams re-established", type="info", timeout=3000)
        else:
            ui.notify("Failed to send reboot command", type="negative")

    def _drain_telemetry(self):
        """Non-blocking drain of the pymavlink buffer — call after parameter load to populate _raw."""
        for _ in range(20):
            try:
                if not self.service.update_telemetry():
                    break
            except Exception:
                break

    def _mark_disconnected(self, reason: str = ""):
        """Clean up after an unexpected device disconnect. Safe to call multiple times."""
        if not self.service.is_connected():
            return  # already handled
        self.service.disconnect()
        msg = f"Device disconnected: {reason}" if reason else "Device disconnected"
        print(f"[disconnect] {msg}")
        try:
            self._set_connect_btn_state(False)
            if self._status_label:
                self._status_label.set_text("● Not connected")
                self._status_label.update()
                self._status_label.classes("text-red-400", remove="text-green-400")
            ui.notify(msg, type="warning")
        except Exception:
            pass  # page context gone (e.g. hot-reload fired mid-operation)

    def _clear_messages(self):
        if self._message_log:
            self._message_log.clear()
        if self._params_msg_log:
            self._params_msg_log.clear()
        self._seen_message_count = 0

    def _clear_params_messages(self):
        if self._params_msg_log:
            self._params_msg_log.clear()

    # ── Timers ────────────────────────────────────────────────────────────────

    def _tick_telemetry(self):
        if not self.service.is_connected() or self._loading_params:
            return
        try:
            self.service.update_telemetry()
            td = self.service.get_telemetry()

            sb = self._statusbar
            if sb:
                if td.armed:
                    sb["armed"].set_text("ARMED")
                    sb["armed"].classes("text-red-400", remove="text-green-400")
                    if self._arm_btn:
                        self._arm_btn._props["label"] = "Disarm"
                        self._arm_btn._props["color"] = "negative"
                        self._arm_btn.update()
                else:
                    sb["armed"].set_text("DISARMED")
                    sb["armed"].classes("text-green-400", remove="text-red-400")
                    if self._arm_btn:
                        self._arm_btn._props["label"] = "Arm"
                        self._arm_btn._props["color"] = "green-4"
                        self._arm_btn.update()
                sb["mode"].set_text(td.mode)
                sb["mode"].update()
                sb["heading"].set_text(f"{td.heading:.0f}°")
                sb["heading"].update()
                sb["roll"].set_text(f"{td.roll:+.1f}°")
                sb["roll"].update()
                sb["pitch"].set_text(f"{td.pitch:+.1f}°")
                sb["pitch"].update()

            t = self._telemetry
            if t:

                def upd(key, text):
                    t[key].set_text(text)
                    t[key].update()

                # GPS
                upd("gps_status", f"Status: {self.service.get_gps_status()}")
                upd("gps_lat", f"Lat:       {td.gps_lat:.6f}°")
                upd("gps_lon", f"Lon:       {td.gps_lon:.6f}°")
                upd("gps_alt", f"Alt (MSL): {td.gps_alt:.1f} m")
                upd("rel_alt", f"Alt (Rel): {td.rel_alt:.1f} m")
                upd("gps_hdop", f"HDOP:      {td.gps_hdop:.2f}")
                upd("gps_vdop", f"VDOP:      {td.gps_vdop:.2f}")

                # Battery
                upd("bat_v", f"Voltage:   {td.battery_voltage:.2f} V")
                upd("bat_a", f"Current:   {td.battery_current:.1f} A")
                upd("bat_pct", f"Remaining: {td.battery_remaining}%")

                # System
                upd("mode", f"Mode: {td.mode}")
                upd("throttle", f"Throttle: {td.throttle}%")
                if td.armed:
                    t["armed"].set_text("State: ARMED")
                    t["armed"].classes("text-red-400", remove="text-green-400")
                else:
                    t["armed"].set_text("State: DISARMED")
                    t["armed"].classes("text-green-400", remove="text-red-400")

                # Speed & altitude
                upd("airspeed", f"Airspeed:    {td.airspeed:.1f} m/s")
                upd("groundspeed", f"Groundspeed: {td.groundspeed:.1f} m/s")
                climb_arrow = "▲" if td.climb_rate >= 0 else "▼"
                upd("climb_rate", f"Climb rate:  {climb_arrow}{abs(td.climb_rate):.1f} m/s")
                upd("alt_vfr", f"Alt (baro):  {td.alt_vfr:.1f} m")

                # Attitude
                upd("heading", f"Heading:  {td.heading:.0f}°")
                upd("roll", f"Roll:     {td.roll:+.1f}°")
                upd("pitch", f"Pitch:    {td.pitch:+.1f}°")
                upd("yaw_rate", f"Yaw rate: {td.yaw_rate:+.1f}°/s")
                if td.wind_speed > 0:
                    upd("wind", f"Wind:     {td.wind_speed:.1f} m/s @ {td.wind_dir:.0f}°")
                else:
                    upd("wind", "Wind:     —")

                # EKF
                ekf_str = "OK" if td.ekf_ok else "WARN"
                ekf_color = "text-green-400" if td.ekf_ok else "text-yellow-400"
                t["ekf_ok"].set_text(f"Status: {ekf_str}")
                t["ekf_ok"].classes(ekf_color, remove="text-green-400 text-yellow-400")
                upd("ekf_vel", f"Vel var:      {td.ekf_vel_variance:.3f}")
                upd("ekf_pos_h", f"Pos horiz:    {td.ekf_pos_horiz_variance:.3f}")
                upd("ekf_pos_v", f"Pos vert:     {td.ekf_pos_vert_variance:.3f}")
                upd("ekf_compass", f"Compass var:  {td.ekf_compass_variance:.3f}")
                upd("ekf_terrain", f"Terrain var:  {td.ekf_terrain_variance:.3f}")

                # Vibration
                def vib_color(v):
                    return "text-green-400" if v < 30 else ("text-yellow-400" if v < 60 else "text-red-400")

                for axis, val in [("vib_x", td.vib_x), ("vib_y", td.vib_y), ("vib_z", td.vib_z)]:
                    ax = axis[-1].upper()
                    t[axis].set_text(f"{ax}: {val:.1f}")
                    t[axis].classes(vib_color(val), remove="text-green-400 text-yellow-400 text-red-400")
                clip_color = "text-red-400" if td.vib_clip > 0 else "text-green-400"
                t["vib_clip"].set_text(f"Clipping: {td.vib_clip}")
                t["vib_clip"].classes(clip_color, remove="text-green-400 text-red-400")

                # RC / Link
                if td.rssi == 255:
                    upd("rssi", "RSSI: —")
                else:
                    rssi_pct = round(td.rssi / 254 * 100)
                    upd("rssi", f"RSSI: {td.rssi}  ({rssi_pct}%)")

                # Compass
                upd("mag_field", f"Field strength: {td.mag_field_strength:.0f} mG")
        except Exception as e:
            self._mark_disconnected(str(e))

    def _tick_messages(self):
        if not self.service.is_connected():
            return
        try:
            msgs = list(reversed(self.service.get_messages()))
            if len(msgs) > self._seen_message_count:
                for severity, text in msgs[self._seen_message_count :]:
                    line = f"[{severity}] {text.strip(chr(0))}"
                    if self._message_log:
                        self._message_log.push(line)
                    if self._params_msg_log:
                        self._params_msg_log.push(line)
                self._seen_message_count = len(msgs)
        except Exception:
            pass

    def _tick_raw(self):
        if not self.service.is_connected() or self._raw_table is None:
            return
        try:
            import time as _time

            now = _time.time()
            raw = self.service.get_raw_mavlink()
            query = self._raw_filter.strip()

            # Build filter predicate
            if query:
                try:
                    pat = re.compile(query, re.IGNORECASE)

                    def match(t, f, v):
                        return pat.search(t) or pat.search(f) or pat.search(str(v))
                except re.error:
                    ql = query.lower()

                    def match(t, f, v):
                        return ql in t.lower() or ql in f.lower() or ql in str(v).lower()
            else:

                def match(t, f, v):
                    return True

            rows = []
            for msg_type, (fields, ts) in sorted(raw.items()):
                age = now - ts
                age_str = f"{age:.1f}s" if age < 60 else f"{age/60:.0f}m"
                first = True
                for field, value in sorted(fields.items()):
                    val_str = str(value)
                    if not match(msg_type, field, val_str):
                        continue
                    key = f"{msg_type}.{field}"
                    prev = self._raw_prev.get(key)
                    if prev != val_str:
                        self._raw_changed[key] = now
                        self._raw_prev[key] = val_str
                    changed_recently = (now - self._raw_changed.get(key, 0)) < 2.0
                    display_val = f"● {val_str}" if changed_recently else val_str
                    rows.append(
                        {
                            "key": key,
                            "type": msg_type if first else "",
                            "field": field,
                            "value": display_val,
                            "age": age_str if first else "",
                        }
                    )
                    first = False

            self._raw_table.rows = rows
            self._raw_table.update()

            # Update message count label
            n_types = len([r for r in rows if r["type"]])
            n_fields = len(rows)
            self._raw_msg_count.set_text(f"{n_types} message types  ·  {n_fields} fields")
            self._raw_msg_count.update()
        except Exception:
            pass
