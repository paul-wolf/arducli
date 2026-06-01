"""NiceGUI web interface for ArduCLI."""

import asyncio
import re
from collections import OrderedDict
from typing import Optional

from nicegui import ui

from models import ConnectionConfig
from services import MAVLinkService, ParameterMetadataService, ParamMeta


class WebInterface:
    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.service = MAVLinkService(config)
        self._meta_service = ParameterMetadataService()
        self._param_rows: list = []
        self._recently_accessed: OrderedDict = OrderedDict()
        self._recently_modified: OrderedDict = OrderedDict()
        self._selected_param: Optional[str] = None
        self._selected_meta: Optional[ParamMeta] = None
        self._seen_message_count: int = 0
        self._filter_text: str = ""
        self._connecting: bool = False
        self._loading_params: bool = False
        # UI refs
        self._status_label = None
        self._param_table = None
        self._edit_name = None
        self._edit_value = None
        self._detail_col = None  # dynamic description/range/bitmask/enum section
        self._recent_accessed_col = None
        self._recent_modified_col = None
        self._connect_btn = None
        self._message_log = None
        self._params_msg_log = None
        self._telemetry = {}
        self._statusbar = {}

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
            conn_input = (
                ui.input(
                    placeholder="Connection string  (blank = auto-serial,  udpin:0.0.0.0:14550,  tcp:192.168.1.5:5760)"
                )
                .classes("font-mono text-sm")
                .props("dense outlined dark")
                .style("min-width: 420px")
            )
            self._connect_btn = ui.button("Connect", on_click=lambda: self._do_connect(conn_input.value)).props(
                "color=primary dense"
            )
            ui.button("Disconnect", on_click=self._do_disconnect).props("color=negative dense outline")
            ui.button("Load Params", on_click=self._load_parameters).props("color=secondary dense")

        # Always-visible status strip
        sb = self._statusbar
        with ui.row().classes("w-full items-center gap-4 px-4 py-1 bg-gray-800").style(
            "border-bottom: 1px solid #374151;"
        ):
            sb["armed"] = ui.label("DISARMED").classes("font-mono text-sm font-bold text-green-400")
            ui.label("|").classes("text-gray-600")
            with ui.row().classes("items-center gap-1"):
                ui.label("Mode:").classes("text-gray-400 text-xs font-mono")
                sb["mode"] = ui.label("—").classes("font-mono text-sm text-white")
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

        with ui.tab_panels(tabs, value=t_params).classes("w-full bg-gray-900").style("flex: 1; overflow: hidden;"):
            with ui.tab_panel(t_params).classes("p-2"):
                self._build_params_panel()
            with ui.tab_panel(t_status).classes("p-4"):
                self._build_status_panel()
            with ui.tab_panel(t_messages).classes("p-2"):
                self._build_messages_panel()

        ui.timer(0.5, self._tick_telemetry)
        ui.timer(1.0, self._tick_messages)

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
        with ui.grid(columns=2).classes("w-full gap-4"):
            with ui.card().classes("bg-gray-800 text-white"):
                ui.label("GPS").classes("font-bold text-blue-300 mb-2")
                t["gps_status"] = ui.label("Status: —").classes("font-mono text-sm")
                t["gps_lat"] = ui.label("Lat: —").classes("font-mono text-sm")
                t["gps_lon"] = ui.label("Lon: —").classes("font-mono text-sm")
                t["gps_alt"] = ui.label("Alt: —").classes("font-mono text-sm")
            with ui.card().classes("bg-gray-800 text-white"):
                ui.label("Battery").classes("font-bold text-green-300 mb-2")
                t["bat_v"] = ui.label("Voltage: —").classes("font-mono text-sm")
                t["bat_a"] = ui.label("Current: —").classes("font-mono text-sm")
                t["bat_pct"] = ui.label("Remaining: —").classes("font-mono text-sm")
            with ui.card().classes("bg-gray-800 text-white"):
                ui.label("Attitude").classes("font-bold text-purple-300 mb-2")
                t["heading"] = ui.label("Heading: —").classes("font-mono text-sm")
                t["roll"] = ui.label("Roll: —").classes("font-mono text-sm")
                t["pitch"] = ui.label("Pitch: —").classes("font-mono text-sm")
            with ui.card().classes("bg-gray-800 text-white"):
                ui.label("System").classes("font-bold text-orange-300 mb-2")
                t["mode"] = ui.label("Mode: —").classes("font-mono text-sm")
                t["armed"] = ui.label("State: DISARMED").classes("font-mono text-sm text-green-400")

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
        if self._connect_btn:
            self._connect_btn.props(remove="loading")
            self._connect_btn.update()
        if ok:
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
            self._status_label.set_text("● Not connected")
            self._status_label.update()
            self._status_label.classes("text-red-400", remove="text-green-400")
            ui.notify("Connection failed", type="negative")

    async def _do_disconnect(self):
        self.service.disconnect()
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

    def _mark_disconnected(self, reason: str = ""):
        """Clean up after an unexpected device disconnect. Safe to call multiple times."""
        if not self.service.is_connected():
            return  # already handled
        self.service.disconnect()
        if self._status_label:
            self._status_label.set_text("● Not connected")
            self._status_label.update()
            self._status_label.classes("text-red-400", remove="text-green-400")
        msg = f"Device disconnected: {reason}" if reason else "Device disconnected"
        ui.notify(msg, type="warning")
        print(f"[disconnect] {msg}")

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
                else:
                    sb["armed"].set_text("DISARMED")
                    sb["armed"].classes("text-green-400", remove="text-red-400")
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
                t["gps_status"].set_text(f"Status: {self.service.get_gps_status()}")
                t["gps_status"].update()
                t["gps_lat"].set_text(f"Lat:  {td.gps_lat:.6f}°")
                t["gps_lat"].update()
                t["gps_lon"].set_text(f"Lon:  {td.gps_lon:.6f}°")
                t["gps_lon"].update()
                t["gps_alt"].set_text(f"Alt:  {td.gps_alt:.1f} m")
                t["gps_alt"].update()
                t["bat_v"].set_text(f"Voltage:    {td.battery_voltage:.2f} V")
                t["bat_v"].update()
                t["bat_a"].set_text(f"Current:    {td.battery_current:.1f} A")
                t["bat_a"].update()
                t["bat_pct"].set_text(f"Remaining:  {td.battery_remaining}%")
                t["bat_pct"].update()
                t["heading"].set_text(f"Heading:  {td.heading:.0f}°")
                t["heading"].update()
                t["roll"].set_text(f"Roll:     {td.roll:+.1f}°")
                t["roll"].update()
                t["pitch"].set_text(f"Pitch:    {td.pitch:+.1f}°")
                t["pitch"].update()
                t["mode"].set_text(f"Mode: {td.mode}")
                t["mode"].update()
                if td.armed:
                    t["armed"].set_text("State: ARMED")
                    t["armed"].classes("text-red-400", remove="text-green-400")
                else:
                    t["armed"].set_text("State: DISARMED")
                    t["armed"].classes("text-green-400", remove="text-red-400")
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
