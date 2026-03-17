"""
main_gui.py — Crypto Tax Pro 2026
7-step wizard UI built with Flet 0.24.x
"""
import flet as ft
import os
import sys
import threading
import datetime
from dataclasses import dataclass, field
from decimal import Decimal

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.exchange_manager import get_enabled_exchanges, get_exchange
from src.data_loader import load_ledgers, group_entries_by_event, validate_file
from src.wallet_mapper import get_wallet_summary
from src.fifo_engine import FIFOEngine
from src.anomaly_detector import detect_anomalies, get_anomaly_summary
from src.tax_reporter import build_form_8949_csv, build_turbotax_csv, build_audit_log
from src.form_1099_da_importer import parse_1099_da_csv
from src.charts import get_asset_breakdown, get_tax_summary, get_monthly_breakdown

# ── Theme ──────────────────────────────────────────────────────────────────────
BG_DARK   = "#0d0d1a"
BG_MID    = "#13132a"
BG_CARD   = "#0a0a18"
BORDER    = "#2a2a5a"
AMBER     = ft.colors.AMBER_400
GREY_TEXT = ft.colors.GREY_500

STEP_LABELS = ["Exchange", "Load Files", "Wallets", "Config", "Process", "Review", "Download"]


# ── Shared wizard state ────────────────────────────────────────────────────────
@dataclass
class WizardState:
    selected_exchanges: list = field(default_factory=list)
    uploaded_files: list = field(default_factory=list)
    wallet_summary: list = field(default_factory=list)
    available_years: list = field(default_factory=list)  # years found in loaded data
    calc_method: str = "FIFO"
    transfer_mode: str = "auto"
    tax_year: int = 2025
    period_start: datetime.date = field(default_factory=lambda: datetime.date(2025, 1, 1))
    period_end: datetime.date = field(default_factory=lambda: datetime.date(2025, 12, 31))
    engine: object = None
    anomalies: list = field(default_factory=list)
    report_data: dict = field(default_factory=dict)
    form_1099_da_records: list = field(default_factory=list)
    da_file_path: str = ""
    safe_harbor_records: list = field(default_factory=list)
    sh_file_path: str = ""
    security_tokens: set = field(default_factory=lambda: {"ADA", "SOL", "MATIC", "ALGO", "FIL", "ATOM", "SAND", "MANA", "CHZ", "COTI"})


# ── Common UI helpers ──────────────────────────────────────────────────────────
def card(content, padding=20, border_color=BORDER, bgcolor=BG_CARD, radius=12):
    return ft.Container(
        content=content,
        padding=ft.padding.all(padding),
        bgcolor=bgcolor,
        border_radius=radius,
        border=ft.border.all(1, border_color),
    )


def section_label(text):
    return ft.Text(text, size=10, color=GREY_TEXT, weight=ft.FontWeight.W_700)


def ghost_btn(label, on_click, icon=None):
    items = []
    if icon:
        items.append(ft.Icon(icon, size=16, color=ft.colors.GREY_400))
    items.append(ft.Text(label, size=13, color=ft.colors.GREY_400))
    return ft.ElevatedButton(
        content=ft.Row(items, spacing=6, tight=True),
        on_click=on_click,
        style=ft.ButtonStyle(
            bgcolor={ft.ControlState.DEFAULT: "#1a1a3a"},
            color={ft.ControlState.DEFAULT: ft.colors.GREY_400},
            padding=ft.padding.symmetric(horizontal=16, vertical=13),
            shape=ft.RoundedRectangleBorder(radius=8),
            side={ft.ControlState.DEFAULT: ft.BorderSide(1, BORDER)},
        ),
    )


# ── Step indicator top bar ─────────────────────────────────────────────────────
def build_step_indicator(current_step: int) -> ft.Container:
    dots = []
    for i, label in enumerate(STEP_LABELS):
        if i < current_step:
            color, icon = ft.colors.GREEN_400, ft.icons.CHECK_CIRCLE
        elif i == current_step:
            color, icon = AMBER, ft.icons.RADIO_BUTTON_ON
        else:
            color, icon = ft.colors.GREY_700, ft.icons.RADIO_BUTTON_OFF

        dots.append(ft.Column(
            [ft.Icon(icon, color=color, size=18), ft.Text(label, size=9, color=color)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2,
        ))
        if i < len(STEP_LABELS) - 1:
            dots.append(ft.Container(
                width=36, height=1,
                bgcolor=ft.colors.GREEN_400 if i < current_step else BORDER,
                margin=ft.margin.only(bottom=8),
            ))

    return ft.Container(
        content=ft.Row(dots, alignment=ft.MainAxisAlignment.CENTER,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.padding.symmetric(horizontal=30, vertical=14),
        bgcolor=BG_MID,
        border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
    )


# ── STEP 0: EULA ──────────────────────────────────────────────────────────────
def build_eula(page: ft.Page, on_accept):
    accept_btn = ft.ElevatedButton(
        content=ft.Row([
            ft.Icon(ft.icons.ROCKET_LAUNCH, size=16),
            ft.Text("Accept & Get Started", size=14, weight=ft.FontWeight.W_600),
        ], spacing=8, tight=True),
        on_click=on_accept,
        style=ft.ButtonStyle(
            bgcolor={ft.ControlState.DEFAULT: AMBER},
            color={ft.ControlState.DEFAULT: ft.colors.BLACK},
            padding=ft.padding.symmetric(horizontal=32, vertical=16),
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )
    
    def feature_row(icon, title, desc):
        return ft.Row([
            ft.Container(
                content=ft.Icon(icon, color=AMBER, size=24),
                padding=10, bgcolor="#1a1a00", border_radius=8
            ),
            ft.Column([
                ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                ft.Text(desc, size=12, color=GREY_TEXT),
            ], spacing=2, expand=True)
        ], spacing=15, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    return ft.Container(
        expand=True,
        alignment=ft.alignment.Alignment(0, 0),
        content=ft.Container(
            width=720,
            padding=ft.padding.all(40),
            bgcolor=BG_MID,
            border_radius=20,
            border=ft.border.all(1, BORDER),
            content=ft.Column([
                ft.Row([ft.Icon(ft.icons.ACCOUNT_BALANCE, color=AMBER, size=48)],
                       alignment=ft.MainAxisAlignment.CENTER),
                ft.Text("Welcome to Crypto Tax Pro 2026", size=32, weight=ft.FontWeight.BOLD,
                        color=ft.colors.WHITE, text_align=ft.TextAlign.CENTER),
                ft.Text("The complete solution for IRS-compliant crypto tax reporting",
                        size=14, color=GREY_TEXT, text_align=ft.TextAlign.CENTER),
                
                ft.Container(height=20),
                
                # Features Grid
                ft.Row([
                    ft.Column([
                        feature_row(ft.icons.VERIFIED, "IRS Compliant Reports", "Generates Form 8949 and TurboTax imports automatically"),
                        feature_row(ft.icons.SETTINGS_APPLICATIONS, "Dual-Engine Calculation", "Full support for FIFO, HIFO, and LIFO methodologies"),
                    ], spacing=20, expand=True),
                    ft.Column([
                        feature_row(ft.icons.AUTORENEW, "Smart Detection", "Identifies Wash Sales and reconciles 1099-DA forms natively"),
                        feature_row(ft.icons.SECURITY, "Total Privacy", "100% local processing. No data is ever sent to the cloud."),
                    ], spacing=20, expand=True),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                ft.Container(height=20),
                ft.Divider(color=BORDER, height=1),
                ft.Container(height=10),

                card(
                    ft.Column([
                        ft.Text("End User License Agreement (EULA)", size=12, weight=ft.FontWeight.BOLD, color=ft.colors.GREY_400),
                        ft.Text(
                            "By using this application you acknowledge:\n"
                            "1. NOT PROFESSIONAL ADVICE: The developer does not operate as a CPA. This software is a mechanical calculation tool.\n"
                            "2. HOLD HARMLESS: You agree not to hold the developer liable for any IRS penalties or discrepancies based on these results.\n"
                            "3. 2026 CHANGES: Verify 1099-DA accuracy with your exchange and apply manual adjustments to Form 8949 if needed.",
                            size=11, color=ft.colors.GREY_500,
                        )
                    ], spacing=8),
                    bgcolor="#0a0a18",
                    padding=15
                ),
                ft.Container(height=10),
                accept_btn,
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        ),
    )


# ── STEP 1: EXCHANGE SELECTOR ─────────────────────────────────────────────────
def build_exchange_step(page: ft.Page, state: WizardState, on_next):
    exchanges = get_enabled_exchanges()

    guide_text = ft.Text(
        "Select an exchange above to see the export guide.",
        size=13, color=ft.colors.GREY_500,
    )

    # Concrete button — we mutate .disabled directly, no Ref needed
    continue_btn = ft.ElevatedButton(
        content=ft.Row([
            ft.Icon(ft.icons.ARROW_FORWARD, size=16),
            ft.Text("Continue", size=13, weight=ft.FontWeight.W_700),
        ], spacing=6, tight=True),
        on_click=on_next,
        disabled=True,
        style=ft.ButtonStyle(
            bgcolor={ft.ControlState.DEFAULT: AMBER, ft.ControlState.DISABLED: "#333344"},
            color={ft.ControlState.DEFAULT: ft.colors.BLACK, ft.ControlState.DISABLED: ft.colors.GREY_600},
            padding=ft.padding.symmetric(horizontal=20, vertical=13),
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )

    grid = ft.Column(controls=[], spacing=12)

    def refresh_all():
        """Rebuild exchange cards and sync button + guide."""
        grid.controls.clear()
        row_items = []
        for ex in exchanges:
            selected = ex.key in state.selected_exchanges
            status_label = (
                "Coming soon" if ex.coming_soon
                else ("✓ Selected" if selected else "Available")
            )
            status_color = (
                ft.colors.GREY_600 if ex.coming_soon
                else (ft.colors.AMBER_400 if selected else ft.colors.GREEN_400)
            )
            row_items.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ex.icon,
                                color=ex.color if not ex.coming_soon else ft.colors.GREY_700,
                                size=30),
                        ft.Text(ex.name, size=13, weight=ft.FontWeight.W_600,
                                color=ft.colors.WHITE if not ex.coming_soon else ft.colors.GREY_700),
                        ft.Text(status_label, size=10, color=status_color),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    padding=ft.padding.all(18),
                    border_radius=12,
                    bgcolor="#1a1a3a" if selected else BG_CARD,
                    border=ft.border.all(2, AMBER if selected else BORDER),
                    on_click=(lambda e, k=ex.key: on_toggle(k)) if not ex.coming_soon else None,
                    opacity=1.0 if not ex.coming_soon else 0.45,
                    width=145,
                )
            )
        for i in range(0, len(row_items), 3):
            grid.controls.append(ft.Row(row_items[i:i + 3], spacing=12))

        # Update guide text
        selected_cfgs = [get_exchange(k) for k in state.selected_exchanges if get_exchange(k)]
        guide_text.value = (
            "\n".join(selected_cfgs[-1].guide)
            if selected_cfgs
            else "Select an exchange above to see the export guide."
        )

        # KEY FIX: update the concrete button's disabled property
        continue_btn.disabled = len(state.selected_exchanges) == 0
        page.update()

    def on_toggle(key):
        if key in state.selected_exchanges:
            state.selected_exchanges.remove(key)
        else:
            state.selected_exchanges.append(key)
        refresh_all()

    refresh_all()  # initial render

    return ft.Column([
        ft.Text("Step 1 — Select Your Exchange(s)", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
        ft.Text("Choose which platforms you traded on during 2025.", size=13, color=GREY_TEXT),
        ft.Container(height=8),
        grid,
        ft.Container(height=8),
        card(ft.Column([section_label("EXPORT GUIDE"), ft.Container(height=4), guide_text], spacing=6)),
        ft.Container(height=12),
        ft.Row([ft.Container(expand=True), continue_btn]),
    ], spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)


# ── STEP 2: FILE LOADING ──────────────────────────────────────────────────────
def build_file_step(page: ft.Page, state: WizardState, on_back, on_next, input_picker):
    file_list = ft.Column(spacing=8)

    # Concrete button — we mutate .disabled directly, no Ref needed
    continue_btn = ft.ElevatedButton(
        content=ft.Row([ft.Icon(ft.icons.ARROW_FORWARD, size=16), ft.Text("Continue", size=13, weight=ft.FontWeight.W_700)], spacing=6, tight=True),
        on_click=on_next,
        disabled=True,
        style=ft.ButtonStyle(
            bgcolor={ft.ControlState.DEFAULT: AMBER, ft.ControlState.DISABLED: "#333344"},
            color={ft.ControlState.DEFAULT: ft.colors.BLACK, ft.ControlState.DISABLED: ft.colors.GREY_600},
            padding=ft.padding.symmetric(horizontal=20, vertical=13),
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )

    def refresh_list():
        file_list.controls.clear()
        for i, f in enumerate(state.uploaded_files):
            v = f.get("validation")
            if v is None:
                badge_color, badge_text = ft.colors.GREY_600, "PENDING"
            elif v.status == "valid":
                badge_color, badge_text = ft.colors.GREEN_400, "VALID"
            elif v.status == "warning":
                badge_color, badge_text = ft.colors.AMBER_400, "WARNING"
            else:
                badge_color, badge_text = ft.colors.RED_400, "ERROR"

            date_range = f"{v.date_start} → {v.date_end}" if v and v.date_start else ""

            file_list.controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                    bgcolor=BG_CARD, border_radius=10,
                    border=ft.border.all(1, badge_color if v else BORDER),
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.icons.INSERT_DRIVE_FILE_OUTLINED, color=ft.colors.BLUE_300, size=18),
                            ft.Column([
                                ft.Text(f["name"], size=13, weight=ft.FontWeight.W_600, color=ft.colors.WHITE),
                                ft.Row([
                                    ft.Text(f"Wallet: {f['wallet']}", size=11, color=GREY_TEXT),
                                    ft.Text(f"  {date_range}", size=11, color=ft.colors.GREY_600),
                                    ft.Container(
                                        content=ft.Text(badge_text, size=9, color=ft.colors.BLACK, weight=ft.FontWeight.BOLD),
                                        bgcolor=badge_color, border_radius=4,
                                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                    ),
                                ], spacing=4),
                            ], spacing=2, expand=True),
                            ft.IconButton(ft.icons.CLOSE, icon_color=ft.colors.RED_400,
                                          icon_size=16, on_click=lambda _, idx=i: remove(idx)),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text(v.message if v and v.message else "", size=11,
                                color=ft.colors.AMBER_300 if v and v.message and v.status == "warning" else ft.colors.RED_300,
                                visible=bool(v and v.message)),
                    ], spacing=4),
                )
            )
        continue_btn.disabled = len(state.uploaded_files) == 0
        page.update()

    def remove(idx):
        state.uploaded_files.pop(idx)
        refresh_list()

    def on_files_picked(e: ft.FilePickerResultEvent):
        if e.files:
            ex_key = state.selected_exchanges[0] if state.selected_exchanges else "kraken"
            for f in e.files:
                wallet = f.name.split("_")[0].capitalize()
                validation = validate_file(f.path, ex_key)
                state.uploaded_files.append({
                    "path": f.path, "wallet": wallet, "name": f.name,
                    "exchange_key": ex_key, "validation": validation,
                })
        refresh_list()

    input_picker.on_result = on_files_picked

    hint_text = ""
    if state.selected_exchanges:
        cfg = get_exchange(state.selected_exchanges[0])
        if cfg:
            hint_text = cfg.guide[0]

    return ft.Column([
        ft.Text("Step 2 — Load Your Ledger Files", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
        ft.Text("Load one CSV per exchange. Only Ledger exports are accepted.", size=13, color=GREY_TEXT),
        ft.Container(height=4),
        (card(ft.Column([section_label("QUICK GUIDE"), ft.Text(hint_text, size=12, color=ft.colors.BLUE_200)], spacing=4))
         if hint_text else ft.Container()),
        ft.Container(height=4),
        ft.ElevatedButton(
            content=ft.Row([ft.Icon(ft.icons.ADD, size=16), ft.Text("Add Ledger CSV", size=13)], spacing=6),
            on_click=lambda _: input_picker.pick_files(allow_multiple=True),
            style=ft.ButtonStyle(
                bgcolor={ft.ControlState.DEFAULT: "#1a2a4a"},
                color={ft.ControlState.DEFAULT: ft.colors.BLUE_200},
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
        ),
        file_list,
        ft.Container(height=8),
        ft.Row([
            ghost_btn("Back", on_back, ft.icons.ARROW_BACK),
            ft.Container(expand=True),
            continue_btn,
        ]),
    ], spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)


# ── STEP 3: WALLET MAPPING ────────────────────────────────────────────────────
def build_wallet_step(page: ft.Page, state: WizardState, on_back, on_next):
    rows = []
    for w in state.wallet_summary:
        rows.append(
            ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                bgcolor=BG_CARD, border_radius=10, border=ft.border.all(1, BORDER),
                content=ft.Row([
                    ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, color=ft.colors.BLUE_300, size=20),
                    ft.Column([
                        ft.Text(w["wallet_id"], size=13, weight=ft.FontWeight.W_600, color=ft.colors.WHITE),
                        ft.Text(
                            f"Assets: {', '.join(w['assets'][:5])}  •  "
                            f"In: {w['inflows']}  Out: {w['outflows']}",
                            size=11, color=GREY_TEXT,
                        ),
                    ], spacing=2, expand=True),
                    ft.Container(
                        content=ft.Text(f"⚠ {w['orphan_count']} orphan inflows", size=10,
                                        color=ft.colors.BLACK, weight=ft.FontWeight.BOLD),
                        bgcolor=ft.colors.AMBER_400, border_radius=4,
                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                        visible=w["has_issues"],
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
        )

    if not rows:
        rows.append(ft.Text("No wallets detected. Go back and load at least one valid file.", size=13, color=ft.colors.RED_300))

    orphan_count = sum(w["orphan_count"] for w in state.wallet_summary)
    notice = ft.Container()
    if orphan_count > 0:
        notice = card(
            ft.Column([
                ft.Row([ft.Icon(ft.icons.WARNING_AMBER, color=ft.colors.AMBER_400, size=20),
                        ft.Text("Orphan Inflows Detected", size=14, weight=ft.FontWeight.BOLD, color=ft.colors.AMBER_400)]),
                ft.Text(
                    f"{orphan_count} sale(s) have no recorded purchase in that wallet. "
                    "These are likely transfers from another wallet. "
                    "The engine will assign $0 cost basis and flag them in the audit trail.",
                    size=13, color=ft.colors.GREY_300,
                ),
            ], spacing=8),
            bgcolor="#1a1000", border_color=ft.colors.AMBER_800,
        )

    return ft.Column([
        ft.Text("Step 3 — Wallet Identification", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
        ft.Text("Review detected wallets before calculation.", size=13, color=GREY_TEXT),
        ft.Container(height=6),
        *rows,
        notice,
        ft.Container(height=10),
        ft.Row([
            ghost_btn("Back", on_back, ft.icons.ARROW_BACK),
            ft.Container(expand=True),
            ft.ElevatedButton(
                content=ft.Row([ft.Icon(ft.icons.ARROW_FORWARD, size=16), ft.Text("Continue", size=13, weight=ft.FontWeight.W_700)], spacing=6, tight=True),
                on_click=on_next,
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: AMBER},
                    color={ft.ControlState.DEFAULT: ft.colors.BLACK},
                    padding=ft.padding.symmetric(horizontal=20, vertical=13),
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
            ),
        ]),
    ], spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)


# ── STEP 4: CALCULATION CONFIG ────────────────────────────────────────────────
def build_config_step(page: ft.Page, state: WizardState, on_back, on_next):
    def on_method_change(e):
        state.calc_method = e.control.value

    da_status_text = ft.Text(
        f"  1099-DA file   : Not loaded" if not state.da_file_path else f"  1099-DA file   : {os.path.basename(state.da_file_path)}",
        size=12, font_family="monospace", 
        color=ft.colors.GREEN_400 if state.da_file_path else GREY_TEXT
    )

    def pick_da_file(e: ft.FilePickerResultEvent):
        if e.files:
            path = e.files[0].path
            state.da_file_path = path
            try:
                state.form_1099_da_records = parse_1099_da_csv(path)
                da_status_text.value = f"  1099-DA file   : {os.path.basename(path)} ({len(state.form_1099_da_records)} records)"
                da_status_text.color = ft.colors.GREEN_400
            except Exception as ex:
                da_status_text.value = f"  1099-DA file   : Error loading file"
                da_status_text.color = ft.colors.RED_400
            page.update()

    da_picker = ft.FilePicker(on_result=pick_da_file)
    page.overlay.append(da_picker)

    sh_status_text = ft.Text(
        f"  Safe Harbor file : Not loaded" if not state.sh_file_path else f"  Safe Harbor file : {os.path.basename(state.sh_file_path)}",
        size=12, font_family="monospace", 
        color=ft.colors.GREEN_400 if state.sh_file_path else GREY_TEXT
    )

    def pick_sh_file(e: ft.FilePickerResultEvent):
        if e.files:
            path = e.files[0].path
            state.sh_file_path = path
            try:
                from src.safe_harbor_importer import parse_safe_harbor_csv
                state.safe_harbor_records = parse_safe_harbor_csv(path)
                sh_status_text.value = f"  Safe Harbor CSV : {os.path.basename(path)} ({len(state.safe_harbor_records)} records)"
                sh_status_text.color = ft.colors.GREEN_400
            except Exception as ex:
                sh_status_text.value = f"  Safe Harbor CSV : Error loading file"
                sh_status_text.color = ft.colors.RED_400
            page.update()

    sh_picker = ft.FilePicker(on_result=pick_sh_file)
    page.overlay.append(sh_picker)

    # ── Period selector helpers ───────────────────────────────────────────────
    # Build preset options from years found in the loaded data.
    # If no data is loaded yet, fall back to the current year.
    _data_years = state.available_years if state.available_years else [datetime.date.today().year]
    PERIOD_PRESETS = {
        f"{year} Tax Year": (datetime.date(year, 1, 1), datetime.date(year, 12, 31))
        for year in sorted(_data_years, reverse=True)  # most recent first
    }
    PERIOD_PRESETS["Custom Range"] = None

    # Determine the initial dropdown value
    def _date_to_preset_key(start, end):
        for label, dates in PERIOD_PRESETS.items():
            if dates and dates[0] == start and dates[1] == end:
                return label
        return "Custom Range"

    period_error_text = ft.Text("", size=11, color=ft.colors.RED_400)
    preview_period_text = ft.Text(
        f"  Period          : {state.period_start}  →  {state.period_end}",
        size=12, font_family="monospace", color=ft.colors.GREEN_400,
    )

    start_field = ft.TextField(
        label="Start Date", hint_text="YYYY-MM-DD",
        value=str(state.period_start),
        width=180, text_size=13,
        border_color=BORDER, focused_border_color=AMBER,
        label_style=ft.TextStyle(color=GREY_TEXT, size=11),
        color=ft.colors.WHITE,
    )
    end_field = ft.TextField(
        label="End Date", hint_text="YYYY-MM-DD",
        value=str(state.period_end),
        width=180, text_size=13,
        border_color=BORDER, focused_border_color=AMBER,
        label_style=ft.TextStyle(color=GREY_TEXT, size=11),
        color=ft.colors.WHITE,
    )

    custom_row = ft.Row([start_field, ft.Text("→", color=GREY_TEXT), end_field, period_error_text],
                        spacing=12, visible=False)

    def _apply_custom_dates(_=None):
        """Validate and save custom start/end dates from the text fields."""
        try:
            s = datetime.date.fromisoformat(start_field.value.strip())
            e = datetime.date.fromisoformat(end_field.value.strip())
            if e < s:
                period_error_text.value = "End date must be ≥ start date."
            else:
                period_error_text.value = ""
                state.period_start = s
                state.period_end = e
                state.tax_year = s.year
                preview_period_text.value = f"  Period          : {s}  →  {e}"
        except ValueError:
            period_error_text.value = "Invalid date format (use YYYY-MM-DD)."
        page.update()

    start_field.on_blur = _apply_custom_dates
    end_field.on_blur = _apply_custom_dates

    def on_period_change(e):
        selected = e.control.value
        dates = PERIOD_PRESETS.get(selected)
        if dates:
            state.period_start, state.period_end = dates
            state.tax_year = dates[0].year
            start_field.value = str(state.period_start)
            end_field.value = str(state.period_end)
            custom_row.visible = False
            preview_period_text.value = f"  Period          : {state.period_start}  →  {state.period_end}"
        else:
            custom_row.visible = True
        page.update()

    period_dropdown = ft.Dropdown(
        value=_date_to_preset_key(state.period_start, state.period_end),
        options=[ft.dropdown.Option(k) for k in PERIOD_PRESETS],
        on_change=on_period_change,
        width=240, text_size=13,
        border_color=BORDER, focused_border_color=AMBER,
        bgcolor="#1a1a3a", color=ft.colors.WHITE,
    )

    return ft.Column([
        ft.Text("Step 4 — Calculation Settings", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
        ft.Text("Configure how the FIFO engine will classify transactions.", size=13, color=GREY_TEXT),
        ft.Container(height=8),
        card(ft.Column([
            section_label("TAX PERIOD"),
            ft.Text("Select the tax year or enter a custom date range.", size=11, color=GREY_TEXT),
            ft.Container(height=8),
            ft.Row([ft.Icon(ft.icons.DATE_RANGE, color=AMBER, size=18), period_dropdown], spacing=10),
            ft.Container(height=6),
            custom_row,
        ], spacing=8)),
        ft.Container(height=8),
        card(ft.Column([
            section_label("IDENTIFICATION METHOD"),
            ft.RadioGroup(
                value=state.calc_method,
                on_change=on_method_change,
                content=ft.Column([
                    ft.Radio(value="FIFO", label="FIFO — First In, First Out  (IRS default, Rev. Proc. 2024-28)"),
                    ft.Radio(value="HIFO", label="HIFO — Highest In, First Out  (minimizes taxable gains)"),
                    ft.Radio(value="LIFO", label="LIFO — Last In, First Out"),
                ], spacing=6),
            ),
        ], spacing=10)),
        ft.Container(height=8),
        card(ft.Column([
            section_label("WASH SALE COMPLIANCE"),
            ft.Text("Define which tokens are subject to SEC wash sale rules (Section 1091). Comma-separated tickers.", size=11, color=GREY_TEXT),
            ft.Container(height=8),
            ft.TextField(
                value=", ".join(sorted(state.security_tokens)),
                hint_text="e.g., ADA, SOL, MATIC",
                width=360, text_size=13,
                border_color=BORDER, focused_border_color=AMBER, color=ft.colors.WHITE,
                on_change=lambda e: setattr(state, 'security_tokens', {t.strip().upper() for t in e.control.value.split(',') if t.strip()})
            ),
        ], spacing=8)),
        ft.Container(height=8),
        card(ft.Column([
            section_label("1099-DA RECONCILIATION (OPTIONAL)"),
            ft.Text("Import Form 1099-DA from your exchange to reconcile cost basis and apply adjustment codes (Code T).", size=11, color=GREY_TEXT),
            ft.Container(height=8),
            ft.Row([
                ft.ElevatedButton(
                    content=ft.Row([ft.Icon(ft.icons.UPLOAD_FILE, size=16), ft.Text("Import 1099-DA CSV", size=12)], spacing=6, tight=True),
                    on_click=lambda _: da_picker.pick_files(allowed_extensions=["csv"]),
                    style=ft.ButtonStyle(
                        bgcolor={ft.ControlState.DEFAULT: "#1a1a3a"},
                        color={ft.ControlState.DEFAULT: ft.colors.GREY_400},
                        padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        shape=ft.RoundedRectangleBorder(radius=6),
                    ),
                ),
            ]),
            da_status_text,
        ], spacing=8)),
        ft.Container(height=8),
        card(ft.Column([
            section_label("SAFE HARBOR INVENTORY (OPTIONAL)"),
            ft.Text("Import pre-2025 cryptocurrency balances to avoid missing basis ($0) during asset transfer or disposition.", size=11, color=GREY_TEXT),
            ft.Container(height=8),
            ft.Row([
                ft.ElevatedButton(
                    content=ft.Row([ft.Icon(ft.icons.UPLOAD_FILE, size=16), ft.Text("Import Safe Harbor CSV", size=12)], spacing=6, tight=True),
                    on_click=lambda _: sh_picker.pick_files(allowed_extensions=["csv"]),
                    style=ft.ButtonStyle(
                        bgcolor={ft.ControlState.DEFAULT: "#1a1a3a"},
                        color={ft.ControlState.DEFAULT: ft.colors.GREY_400},
                        padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        shape=ft.RoundedRectangleBorder(radius=6),
                    ),
                ),
            ]),
            sh_status_text,
        ], spacing=8)),
        ft.Container(height=8),
        card(ft.Column([
            section_label("PRE-CALCULATION PREVIEW"),
            ft.Text(f"  Files loaded    : {len(state.uploaded_files)}", size=12, font_family="monospace", color=ft.colors.GREEN_400),
            ft.Text(f"  Wallets found   : {len(state.wallet_summary)}", size=12, font_family="monospace", color=ft.colors.GREEN_400),
            preview_period_text,
        ], spacing=4), bgcolor="#06060f"),
        ft.Container(height=10),
        ft.Row([
            ghost_btn("Back", on_back, ft.icons.ARROW_BACK),
            ft.Container(expand=True),
            ft.ElevatedButton(
                content=ft.Row([ft.Icon(ft.icons.PLAY_ARROW, size=16), ft.Text("Run Calculation", size=13, weight=ft.FontWeight.W_700)], spacing=6, tight=True),
                on_click=on_next,
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: AMBER},
                    color={ft.ControlState.DEFAULT: ft.colors.BLACK},
                    padding=ft.padding.symmetric(horizontal=20, vertical=13),
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
            ),
        ]),
    ], spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)


# ── STEP 5: PROCESSING ────────────────────────────────────────────────────────
def build_processing_step(page: ft.Page, state: WizardState, on_done, on_error, on_back=None):
    log_text = ft.Text("", size=12, font_family="monospace", selectable=True, color=ft.colors.GREEN_400)
    progress = ft.ProgressBar(color=AMBER, visible=True)
    all_entries_count = {"count": 0}

    def append(line):
        log_text.value += line + "\n"
        page.update()

    # ── single swap container (log ↔ summary) ────────────────────────────────
    log_view = ft.Container(
        content=ft.Column([log_text], scroll=ft.ScrollMode.AUTO, expand=True),
        bgcolor="#06060f",
        border=ft.border.all(1, BORDER),
        border_radius=12,
        padding=16,
        expand=True,
    )
    body = ft.Container(content=log_view, expand=True)

    def show_log():
        body.content = log_view
        page.update()

    def build_summary_view():
        """Re-renders the summary panel and swaps it into body."""
        events = state.engine.taxable_events
        total_events = len(events)
        st = sum((ev.gain_loss for ev in events if ev.term == "Short-Term"), Decimal("0"))
        lt = sum((ev.gain_loss for ev in events if ev.term == "Long-Term"), Decimal("0"))
        net = st + lt
        anomalies = len(state.anomalies)
        wash_sales = state.report_data.get("wash_sales_count", 0)
        da_adjustments = state.report_data.get("1099_discrepancies", 0)

        def gc(val):
            return ft.colors.GREEN_400 if val >= 0 else ft.colors.RED_400

        def kpi_card(label, value, icon_name, color):
            return ft.Container(
                padding=12, bgcolor=BG_CARD, border_radius=8,
                border=ft.border.all(1, BORDER), expand=True,
                content=ft.Column([
                    ft.Icon(icon_name, color=color, size=22),
                    ft.Text(value, size=18, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(label, size=10, color=GREY_TEXT),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)
            )

        summary_col = ft.Column([
            ft.Row([
                ft.Icon(ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN_400, size=26),
                ft.Text("Processing Complete", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_400),
            ], spacing=10),
            ft.Container(height=8),
            ft.Row([
                kpi_card("Entries Loaded", str(all_entries_count["count"]), ft.icons.RECEIPT_LONG, ft.colors.BLUE_300),
                kpi_card("Taxable Events", str(total_events), ft.icons.CALCULATE, ft.colors.CYAN_300),
                kpi_card("Anomalies", str(anomalies), ft.icons.WARNING, ft.colors.AMBER_400),
                kpi_card("Net Gain/Loss", f"${net:,.2f}", ft.icons.TRENDING_UP, gc(net)),
            ], spacing=10),
            ft.Container(height=10),
            card(ft.Column([
                ft.Text("Adjustments & Compliance", size=12, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                ft.Container(height=6),
                ft.Row([ft.Icon(ft.icons.GAVEL, size=16, color=ft.colors.ORANGE_400),
                        ft.Text(f"Short-Term: ${st:,.2f}  |  Long-Term: ${lt:,.2f}", size=11, color=ft.colors.GREY_300)], spacing=8),
                ft.Container(height=4),
                ft.Row([ft.Icon(ft.icons.GAVEL, size=16, color=ft.colors.ORANGE_400),
                        ft.Text(f"Wash Sales: {wash_sales}  |  1099-DA Adjustments: {da_adjustments}", size=11, color=ft.colors.GREY_300)], spacing=8),
            ], spacing=4), bgcolor=BG_CARD, padding=12),
            ft.Container(height=20),
            ft.Row([
                ghost_btn("Back to Config", on_back, ft.icons.ARROW_BACK),
                ft.Container(expand=True),
                ft.ElevatedButton(
                    content=ft.Row([ft.Icon(ft.icons.ARROW_FORWARD, size=16),
                                    ft.Text("Continue to Review", size=13, weight=ft.FontWeight.W_700)],
                                   spacing=6, tight=True),
                    on_click=on_done,
                    style=ft.ButtonStyle(
                        bgcolor={ft.ControlState.DEFAULT: AMBER},
                        color={ft.ControlState.DEFAULT: ft.colors.BLACK},
                        padding=ft.padding.symmetric(horizontal=20, vertical=13),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
            ]),
        ], spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)

        summary_view = ft.Container(content=summary_col, expand=True)
        body.content = summary_view
        page.update()

    # ── background worker ─────────────────────────────────────────────────────
    def run():
        try:
            append("[•] Loading ledger entries...")
            all_entries = []
            for f in state.uploaded_files:
                if f.get("validation") and f["validation"].status == "error":
                    append(f"  [SKIP] {f['name']} — invalid file")
                    continue
                append(f"  [+] {f['wallet']} — {f['name']}")
                all_entries.extend(load_ledgers(
                    f["path"], wallet_id=f["wallet"],
                    exchange_key=f.get("exchange_key", "kraken"),
                ))

            events = group_entries_by_event(all_entries)
            append(f"[•] {len(events)} chronological events grouped.")
            
            # --- Calculate Activity Breakdown Metrics (Filtered by period) ---
            def entry_in_period(e):
                try:
                    if hasattr(e.time, 'date'):
                        d = e.time.date()
                    elif isinstance(e.time, datetime.date):
                        d = e.time
                    else:
                        d = datetime.datetime.strptime(str(e.time).split()[0], "%Y-%m-%d").date()
                    return state.period_start <= d <= state.period_end
                except Exception:
                    return True # Include if we can't parse the date

            period_events = [ev for ev in events if ev and entry_in_period(ev[0])]

            total_rewards = sum(1 for ev in period_events if any(
                getattr(e, "type", "").lower() in ("earn", "reward", "staking") or 
                getattr(e, "subtype", "").lower() in ("earn", "reward", "staking") 
                for e in ev
            ))
            total_deposits = sum(1 for ev in period_events if any(e.type == "deposit" for e in ev) and not any(
                getattr(e, "type", "").lower() in ("earn", "reward", "staking") or 
                getattr(e, "subtype", "").lower() in ("earn", "reward", "staking") 
                for e in ev
            ))
            total_withdrawals = sum(1 for ev in period_events if any(e.type == "withdrawal" for e in ev))
            total_trades = sum(1 for ev in period_events if any(e.type == "trade" for e in ev))
            total_transfers = sum(1 for ev in period_events if any(getattr(e, "type", "") == "transfer" or getattr(e, "subtype", "") == "transfer" for e in ev))
            
            state.report_data["total_deposits"] = total_deposits
            state.report_data["total_rewards"] = total_rewards
            state.report_data["total_withdrawals"] = total_withdrawals
            state.report_data["total_trades"] = total_trades
            state.report_data["total_transfers"] = total_transfers
            
            append(f"[•] Running {state.calc_method} engine (Wallet-by-Wallet)...")

            engine = FIFOEngine(calc_method=state.calc_method)
            if state.safe_harbor_records:
                append(f"[•] Safe Harbor: Injecting {len(state.safe_harbor_records)} pre-existing balances.")
                engine.import_safe_harbor_inventory(state.safe_harbor_records)

            engine.process_events(events)
            state.engine = engine
            total_events = len(engine.taxable_events)
            append(f"  [✓] {total_events} taxable events calculated.")

            # ── Period filter ─────────────────────────────────────────────────
            def _in_period(ev):
                try:
                    sold = datetime.datetime.strptime(ev.date_sold, "%m/%d/%Y").date()
                    return state.period_start <= sold <= state.period_end
                except ValueError:
                    return True  # Keep events with unparseable dates
            
            # Decouple: keep full list for charts, filtered for summary/reports
            state.report_data["all_taxable_events"] = engine.taxable_events
            state.report_data["filtered_taxable_events"] = [ev for ev in engine.taxable_events if _in_period(ev)]
            
            filtered_count = len(state.report_data["filtered_taxable_events"])
            
            # Filter ordinary income (staking/Earn)
            filtered_income = sum(
                amt for dt, amt in engine.ordinary_income_events
                if state.period_start <= (dt.date() if hasattr(dt, 'date') else dt) <= state.period_end
            )
            state.report_data["ordinary_income"] = filtered_income
            
            append(f"  [✓] {filtered_count} events within selected period ({state.period_start} – {state.period_end}).")
            if filtered_count < total_events:
                append(f"  [i] {total_events - filtered_count} events outside period excluded from reports.")

            append("[•] Running anomaly detection...")
            state.anomalies = detect_anomalies(engine.taxable_events, engine.audit_log)

            from src.wash_sale_detector import detect_security_wash_sales
            wash_sales_count = detect_security_wash_sales(state.report_data["filtered_taxable_events"], events, security_tokens=frozenset(state.security_tokens))
            if wash_sales_count > 0:
                append(f"  [!] {wash_sales_count} Wash Sales detected on SEC security tokens.")
            append(f"  [✓] {len(state.anomalies)} anomalies flagged.")

            if state.form_1099_da_records:
                append("[•] Reconciling with 1099-DA records...")
                from src.form_1099_da_importer import reconcile_1099_da
                matched_events, discrepancies = reconcile_1099_da(state.report_data["filtered_taxable_events"], state.form_1099_da_records)
                state.report_data["filtered_taxable_events"] = matched_events
                state.report_data["1099_discrepancies"] = len(discrepancies)
                append(f"  [✓] 1099-DA: {len(discrepancies)} adjustments (Code T).")

            append("[•] Building output files...")
            state.report_data["wash_sales_count"] = wash_sales_count
            state.report_data["form8949"] = build_form_8949_csv(state.report_data["filtered_taxable_events"])
            state.report_data["turbotax"] = build_turbotax_csv(state.report_data["filtered_taxable_events"])
            state.report_data["audit"] = build_audit_log(
                engine.audit_log,
                calc_method=state.calc_method,
                form_8949_csv=state.report_data["form8949"],
                turbotax_csv=state.report_data["turbotax"]
            )

            all_entries_count["count"] = len(all_entries)
            append("[✓] Done. Building summary...")
            progress.visible = False
            page.update()

            build_summary_view()

        except Exception as ex:
            import traceback
            log_text.color = ft.colors.RED_400
            append(f"\n[ERROR] {ex}\n{traceback.format_exc()}")
            progress.visible = False
            page.update()
            on_error(str(ex))

    threading.Thread(target=run, daemon=True).start()

    return ft.Column([
        ft.Text("Step 5 — Processing", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
        ft.Text(f"Running {state.calc_method} engine — wallet-by-wallet mode.", size=13, color=GREY_TEXT),
        ft.Container(height=8),
        progress,
        body,
    ], spacing=10, expand=True)

def build_review_step(page: ft.Page, state: WizardState, on_back, on_next):
    engine = state.engine
    if not engine:
        return ft.Text("No results — go back and re-run.", color=ft.colors.RED_300)

    # Initial variables for build_review_step before first refresh
    all_events = state.report_data.get("all_taxable_events", engine.taxable_events)
    filtered_events = state.report_data.get("filtered_taxable_events", engine.taxable_events)
    
    st = sum((ev.gain_loss for ev in filtered_events if ev.term == "Short-Term"), Decimal("0"))
    lt = sum((ev.gain_loss for ev in filtered_events if ev.term == "Long-Term"), Decimal("0"))
    net = st + lt

    from src.charts import get_asset_breakdown, get_monthly_breakdown, generate_pie_chart_data
    asset_breakdown = get_asset_breakdown(filtered_events)
    monthly_breakdown = get_monthly_breakdown(all_events)
    
    pie_data, _ = generate_pie_chart_data(asset_breakdown)

    def gc(val):
        return ft.colors.GREEN_400 if val >= 0 else ft.colors.RED_400

    def stat_row(label, value, color=ft.colors.WHITE):
        return ft.Row([
            ft.Text(label, size=13, color=GREY_TEXT, expand=True),
            ft.Text(value, size=13, color=color, weight=ft.FontWeight.W_600),
        ])

    view_state = {
        "level": 1,  # 1: Summary, 2A: Assets, 2B: Months, 3A: Asset Detail, 3B: Month Detail
        "selected_asset": None,
        "selected_month": None
    }
    
    main_container = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)

    def refresh_ui(e=None):
        main_container.controls.clear()
        lvl = view_state["level"]

        # Ensure we have the latest data extracted from state
        all_events = state.report_data.get("all_taxable_events", engine.taxable_events)
        filtered_events = state.report_data.get("filtered_taxable_events", engine.taxable_events)
        
        st = sum((ev.gain_loss for ev in filtered_events if ev.term == "Short-Term"), Decimal("0"))
        lt = sum((ev.gain_loss for ev in filtered_events if ev.term == "Long-Term"), Decimal("0"))
        net = st + lt

        from src.charts import get_asset_breakdown, get_monthly_breakdown, generate_pie_chart_data
        asset_breakdown = get_asset_breakdown(filtered_events)
        monthly_breakdown = get_monthly_breakdown(all_events)
        
        pie_data, _ = generate_pie_chart_data(asset_breakdown)

        # ---------------- LEVEL 1: EXECUTIVE SUMMARY ----------------
        if lvl == 1:
            anomaly_controls = []
            if state.anomalies:
                anomaly_controls.append(ft.Container(height=8))
                anomaly_controls.append(section_label(f"ANOMALIES — {len(state.anomalies)} FLAGGED"))
                for a in state.anomalies[:5]:
                    contents = [
                        ft.Row([
                            ft.Icon(ft.icons.WARNING_AMBER, color=ft.colors.AMBER_400, size=16),
                            ft.Text(a.anomaly_type.replace("_", " ").upper(), size=11,
                                    color=ft.colors.AMBER_400, weight=ft.FontWeight.BOLD),
                        ], spacing=6),
                        ft.Text(a.description, size=12, color=ft.colors.GREY_300),
                    ]

                    if a.anomaly_type == "missing_basis" and getattr(a, "term", None) == "Unknown" and a.event_ref:
                        def on_term_change(e, anomaly=a):
                            anomaly.event_ref.term = e.control.value
                            anomaly.resolved = True
                            # Recalculate CSVs on change
                            state.report_data["form8949"] = build_form_8949_csv(state.report_data["filtered_taxable_events"])
                            state.report_data["turbotax"] = build_turbotax_csv(state.report_data["filtered_taxable_events"])
                            state.report_data["audit"] = build_audit_log(
                                state.engine.audit_log,
                                calc_method=state.calc_method,
                                form_8949_csv=state.report_data["form8949"],
                                turbotax_csv=state.report_data["turbotax"]
                            )
                            # Update summary calculations
                        
                        term_dropdown = ft.Dropdown(
                            width=220, height=40, text_size=12,
                            value=a.event_ref.term,
                            options=[
                                ft.dropdown.Option("Unknown", "Unknown (Defaults to Short)"),
                                ft.dropdown.Option("Short-Term"),
                                ft.dropdown.Option("Long-Term"),
                            ],
                            on_change=on_term_change,
                            border_color=BORDER, focused_border_color=AMBER, color=ft.colors.WHITE
                        )
                        contents.append(ft.Row([ft.Text("Select Term:", size=12, color=GREY_TEXT), term_dropdown], spacing=10))

                    anomaly_controls.append(card(
                        ft.Column(contents, spacing=4),
                        bgcolor="#1a1000", border_color=ft.colors.AMBER_800, padding=12,
                    ))
                if len(state.anomalies) > 5:
                    anomaly_controls.append(
                        ft.Text(f"... and {len(state.anomalies) - 5} more — see Audit Trail.", size=12, color=GREY_TEXT)
                    )

            def go_2a(e): view_state["level"] = "2A"; refresh_ui()
            def go_2b(e): view_state["level"] = "2B"; refresh_ui()

            main_container.controls.extend([
                ft.Text("Step 6 — Executive Summary", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                ft.Text("Review the high-level metrics of your calculation.", size=13, color=GREY_TEXT),
                ft.Container(height=6),
                
                card(ft.Column([
                    ft.Row([
                        ft.Column([
                            ft.Text("Net Capital Gain/Loss", size=11, color=GREY_TEXT),
                            ft.Text(f"${net:,.2f}", size=24, color=gc(net), weight=ft.FontWeight.BOLD),
                        ], expand=True),
                        ft.Column([
                            ft.Text("Taxable Events", size=11, color=GREY_TEXT),
                            ft.Text(str(len(filtered_events)), size=18, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
                        ], expand=True),
                    ]),
                    ft.Divider(color=BORDER),
                    stat_row("Short-Term Gain/Loss", f"${st:,.2f}", gc(st)),
                    stat_row("Long-Term Gain/Loss", f"${lt:,.2f}", gc(lt)),
                    stat_row("Ordinary Income (Staking/Earn)", f"${state.report_data.get('ordinary_income', Decimal('0')):,.2f}", ft.colors.BLUE_300),
                    *( [stat_row("1099-DA Adjustments (Code T)", str(state.report_data["1099_discrepancies"]), ft.colors.AMBER_400)] if "1099_discrepancies" in state.report_data else [] ),
                    *( [stat_row("Wash Sales (Code W)", str(state.report_data.get("wash_sales_count", 0)), ft.colors.AMBER_400)] if state.report_data.get("wash_sales_count", 0) > 0 else [] )
                ], spacing=12)),
                
                # --- NEW: Activity Breakdown ---
                ft.Container(height=8),
                section_label("ACTIVITY BREAKDOWN"),
                card(
                    ft.Row([
                        ft.Column([
                            ft.Text("Deposits", size=11, color=GREY_TEXT),
                            ft.Text(str(state.report_data.get("total_deposits", 0)), size=18, color=ft.colors.GREEN_400, weight=ft.FontWeight.W_600),
                        ], expand=True),
                        ft.Column([
                            ft.Text("Rewards", size=11, color=GREY_TEXT),
                            ft.Text(str(state.report_data.get("total_rewards", 0)), size=18, color=ft.colors.AMBER_400, weight=ft.FontWeight.W_600),
                        ], expand=True),
                        ft.Column([
                            ft.Text("Withdrawals", size=11, color=GREY_TEXT),
                            ft.Text(str(state.report_data.get("total_withdrawals", 0)), size=18, color=ft.colors.RED_400, weight=ft.FontWeight.W_600),
                        ], expand=True),
                        ft.Column([
                            ft.Text("Trades", size=11, color=GREY_TEXT),
                            ft.Text(str(state.report_data.get("total_trades", 0)), size=18, color=ft.colors.BLUE_300, weight=ft.FontWeight.W_600),
                        ], expand=True),
                        ft.Column([
                            ft.Text("Transfers", size=11, color=GREY_TEXT),
                            ft.Text(str(state.report_data.get("total_transfers", 0)), size=18, color=ft.colors.GREY_300, weight=ft.FontWeight.W_600),
                        ], expand=True),
                    ]),
                    padding=15, bgcolor="#13132a"
                ),

                ft.Container(height=8),
                ft.Row([
                    ft.ElevatedButton("By Asset ▼", icon=ft.icons.PIE_CHART, on_click=go_2a, expand=True, style=ft.ButtonStyle(bgcolor=ft.ControlState.DEFAULT, color=ft.colors.WHITE)),
                    ft.ElevatedButton("By Month ▼", icon=ft.icons.CALENDAR_MONTH, on_click=go_2b, expand=True, style=ft.ButtonStyle(bgcolor=ft.ControlState.DEFAULT, color=ft.colors.WHITE)),
                ], spacing=10),
                *anomaly_controls,
            ])
            
        # ---------------- LEVEL 2A: ASSET BREAKDOWN ----------------
        elif lvl == "2A":
            asset_rows = []
            for a in asset_breakdown:
                c = gc(a.gain_loss)
                def go_3a(e, asset_name=a.asset):
                    view_state["level"] = "3A"
                    view_state["selected_asset"] = asset_name
                    refresh_ui()
                    
                asset_rows.append(ft.Container(
                    padding=ft.padding.symmetric(vertical=8, horizontal=12),
                    border=ft.border.only(bottom=ft.border.BorderSide(1, BORDER)),
                    on_click=go_3a, ink=True,
                    content=ft.Row([
                        ft.Text(a.asset, size=13, weight=ft.FontWeight.W_500, expand=2),
                        ft.Text(f"{a.event_count} tx", size=11, color=GREY_TEXT, expand=1),
                        ft.Text(f"${a.gain_loss:,.2f}", size=13, color=c, weight=ft.FontWeight.W_600, expand=2),
                        ft.Icon(ft.icons.CHEVRON_RIGHT, size=16, color=GREY_TEXT)
                    ])
                ))
            
            pie_sections = []
            for p in pie_data:
                pct = p["percentage"]
                # Only show label text if slice is large enough to not overlap
                if pct >= 6:
                    title = f"{p['asset']}\n{pct:.0f}%"
                elif pct >= 3:
                    title = f"{pct:.0f}%"  # Only show the percentage, omit asset name
                else:
                    title = ""  # Too small — hide label entirely, rely on list
                pie_sections.append(
                    ft.PieChartSection(
                        value=float(max(1, pct)),
                        color=p["color"],
                        title=title,
                        radius=55,
                        badge=ft.Container(
                            content=ft.Text(p['asset'], size=9, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
                            bgcolor=p["color"],
                            padding=ft.padding.symmetric(horizontal=4, vertical=2),
                            border_radius=4,
                            visible=(pct < 3),  # Only show badge for very small slices
                        ) if pct < 3 else None,
                        title_style=ft.TextStyle(size=10, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
                    )
                )
            
            main_container.controls.extend([
                ft.Row([
                    ghost_btn("Back to Summary", lambda e: (view_state.update(level=1), refresh_ui()), ft.icons.ARROW_BACK),
                ]),
                card(ft.Column([
                    section_label("ASSET BREAKDOWN"),
                    ft.Row([
                        ft.Container(content=ft.PieChart(sections=pie_sections, sections_space=2, center_space_radius=30, expand=True), height=200, expand=1) if len(pie_sections) else ft.Text("No data.", expand=1),
                        ft.Container(content=ft.Column(asset_rows, scroll=ft.ScrollMode.AUTO), height=250, expand=2)
                    ], vertical_alignment=ft.CrossAxisAlignment.START)
                ]))
            ])

        # ---------------- LEVEL 2B: MONTHLY BREAKDOWN ----------------
        elif lvl == "2B":
            from datetime import datetime as _dt
            import calendar
            MONTH_ABBR = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                          7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}

            # ── Determine which months overlap the selected period ─────────────
            def _month_in_period(month_key: str) -> bool:
                try:
                    y, m = int(month_key[:4]), int(month_key[5:])
                    last_day = calendar.monthrange(y, m)[1]
                    month_start = _dt(y, m, 1).date()
                    month_end   = _dt(y, m, last_day).date()
                    return month_start <= state.period_end and month_end >= state.period_start
                except Exception:
                    return True

            sorted_months = sorted(monthly_breakdown.items())

            # ── Bar chart ─────────────────────────────────────────────────────
            all_gains  = [float(d['gain']) for _, d in sorted_months]
            max_abs    = max((abs(v) for v in all_gains), default=1) or 1

            bar_groups = []
            for idx, (month_key, data) in enumerate(sorted_months):
                gain_val  = float(data['gain'])
                in_period = _month_in_period(month_key)
                bar_color = (
                    (ft.colors.GREEN_400 if gain_val >= 0 else ft.colors.RED_400)
                    if in_period else
                    (ft.colors.GREEN_900 if gain_val >= 0 else ft.colors.RED_900)
                )
                bar_groups.append(
                    ft.BarChartGroup(
                        x=idx,
                        bar_rods=[
                            ft.BarChartRod(
                                from_y=0,
                                to_y=gain_val,
                                width=26,
                                color=bar_color,
                                border_radius=ft.border_radius.only(
                                    top_left=4, top_right=4,
                                    bottom_left=4, bottom_right=4,
                                ),
                                tooltip=f"${gain_val:,.2f}",
                            )
                        ],
                    )
                )

            axis_labels = [
                ft.ChartAxisLabel(
                    value=idx,
                    label=ft.Text(
                        f"{MONTH_ABBR.get(int(mk[5:]), mk[5:])} '{mk[2:4]}",
                        size=9,
                        color=ft.colors.WHITE if _month_in_period(mk) else GREY_TEXT,
                    )
                )
                for idx, (mk, _) in enumerate(sorted_months)
            ]

            bar_chart_widget = ft.BarChart(
                bar_groups=bar_groups,
                bottom_axis=ft.ChartAxis(labels=axis_labels, labels_size=22),
                left_axis=ft.ChartAxis(labels_size=40, show_labels=False),
                horizontal_grid_lines=ft.ChartGridLines(
                    color=ft.colors.with_opacity(0.1, ft.colors.WHITE), width=0.5
                ),
                interactive=True,
                max_y=max_abs * 1.2,
                min_y=-max_abs * 1.2,
                bgcolor="transparent",
                expand=True,
            )

            chart_card = card(ft.Column([
                section_label("GAIN / LOSS BY MONTH"),
                ft.Row([
                    ft.Icon(ft.icons.CIRCLE, color=ft.colors.GREEN_400, size=10),
                    ft.Text("Gain  ", size=10, color=GREY_TEXT),
                    ft.Icon(ft.icons.CIRCLE, color=ft.colors.RED_400, size=10),
                    ft.Text("Loss  ", size=10, color=GREY_TEXT),
                    ft.Icon(ft.icons.CIRCLE, color=ft.colors.GREY_700, size=10),
                    ft.Text("Outside selected period", size=10, color=GREY_TEXT),
                ], spacing=4),
                ft.Container(height=6),
                ft.Container(content=bar_chart_widget, height=180),
            ], spacing=6))

            # ── Month cards ───────────────────────────────────────────────────
            month_cards = []
            for month_key, data in sorted_months:
                c         = gc(data['gain'])
                in_period = _month_in_period(month_key)
                try:
                    year, mo = int(month_key[:4]), int(month_key[5:])
                    label    = f"{MONTH_ABBR.get(mo, str(mo))} {year}"
                except Exception:
                    label = month_key

                def go_3b(e, m=month_key):
                    view_state["level"] = "3B"
                    view_state["selected_month"] = m
                    refresh_ui()

                card_bgcolor = BG_CARD if in_period else "#1a1400"
                card_border  = BORDER  if in_period else ft.colors.AMBER_900
                label_color  = ft.colors.WHITE if in_period else GREY_TEXT
                gain_color   = c if in_period else ft.colors.GREY_600

                items = [
                    ft.Text(label, size=13, weight=ft.FontWeight.BOLD, color=label_color),
                    ft.Container(height=4),
                    ft.Text(f"${data['gain']:,.2f}", size=15, weight=ft.FontWeight.BOLD, color=gain_color),
                    ft.Text(f"{data['count']} transactions", size=10, color=GREY_TEXT),
                ]
                if not in_period:
                    items.append(ft.Container(
                        content=ft.Text("Outside period", size=8, color=ft.colors.AMBER_700),
                        bgcolor="#2a1e00", border_radius=4,
                        padding=ft.padding.symmetric(horizontal=4, vertical=2),
                        margin=ft.margin.only(top=4),
                    ))

                month_cards.append(ft.Container(
                    on_click=go_3b, ink=True,
                    padding=ft.padding.symmetric(vertical=12, horizontal=14),
                    border=ft.border.all(1, card_border),
                    border_radius=10,
                    bgcolor=card_bgcolor,
                    content=ft.Column(items, spacing=2,
                                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    width=140,
                ))

            month_grid = ft.Row(month_cards, wrap=True, spacing=10, run_spacing=10)

            main_container.controls.extend([
                ft.Row([ghost_btn("Back to Summary",
                                  lambda e: (view_state.update(level=1), refresh_ui()),
                                  ft.icons.ARROW_BACK)]),
                ft.Text("Monthly Breakdown", size=22, weight=ft.FontWeight.BOLD,
                        color=ft.colors.WHITE),
                ft.Text("Dimmed cards are outside the selected evaluation period.",
                        size=13, color=GREY_TEXT),
                ft.Container(height=6),
                chart_card,
                ft.Container(height=10),
                section_label("MONTH CARDS"),
                ft.Container(height=6),
                month_grid,
            ])

        # ---------------- LEVEL 3B: MONTHLY DETAIL (chart + table) ----------------
        elif lvl == "3B":
            from datetime import datetime as _dt
            from collections import defaultdict
            MONTH_ABBR = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                          7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}

            target = view_state["selected_month"]
            def back_fn(e): view_state["level"] = "2B"; refresh_ui()

            try:
                year, mo = int(target[:4]), int(target[5:])
                month_label = f"{MONTH_ABBR.get(mo, str(mo))} {year}"
            except Exception:
                month_label = target

            # Filter events for this month from ALL history for display
            detail_events = []
            for ev in all_events:
                try:
                    try:
                        ev_dt = _dt.strptime(ev.date_sold, "%m/%d/%Y")
                    except ValueError:
                        ev_dt = _dt.fromisoformat(ev.date_sold)
                    
                    if ev_dt.strftime("%Y-%m") == target:
                        detail_events.append(ev)
                except Exception:
                    pass

            # ── Daily aggregation for bar chart ──────────────────────────
            daily = defaultdict(lambda: Decimal("0"))
            for ev in detail_events:
                try:
                    try:
                        ev_dt = _dt.strptime(ev.date_sold, "%m/%d/%Y")
                    except ValueError:
                        ev_dt = _dt.fromisoformat(ev.date_sold)
                    day = ev_dt.strftime("%d")
                    daily[day] += ev.gain_loss
                except Exception:
                    pass

            sorted_days = sorted(daily.keys())
            day_gains = [daily[d] for d in sorted_days]
            max_abs = max((abs(v) for v in day_gains), default=Decimal("1"))
            bar_height = 100

            bar_items = []
            for day, gain in zip(sorted_days, day_gains):
                ratio = float(abs(gain) / max_abs) if max_abs else 0
                filled_h = max(3, int(bar_height * ratio))
                color = ft.colors.GREEN_400 if gain >= 0 else ft.colors.RED_400
                bar_items.append(ft.Column([
                    ft.Container(
                        width=18,
                        height=filled_h,
                        bgcolor=color,
                        border_radius=ft.border_radius.only(top_left=3, top_right=3),
                        tooltip=f"Day {day}: ${gain:,.2f}",
                    ),
                    ft.Text(day, size=8, color=GREY_TEXT, text_align=ft.TextAlign.CENTER, width=18),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2))

            bar_chart_row = ft.Row(
                bar_items,
                scroll=ft.ScrollMode.AUTO,
                vertical_alignment=ft.CrossAxisAlignment.END,
                height=bar_height + 20,
            ) if bar_items else ft.Text("No daily data available.", color=GREY_TEXT)

            # ── Pagination state ─────────────────────────────────────────
            page_state = {"page": 1, "per_page": 10}

            table_container = ft.Container(expand=True)

            def render_table():
                page_num = page_state["page"]
                per_page = page_state["per_page"]
                total = len(detail_events)
                total_pages = max(1, (total + per_page - 1) // per_page)
                start = (page_num - 1) * per_page
                page_events = detail_events[start: start + per_page]

                rows = []
                for ev in page_events:
                    tooltip_text = f"Proceeds: ${ev.proceeds:,.2f}\nBasis: ${ev.cost_basis:,.2f}"
                    if ev.adjustment_code:
                        tooltip_text += f"\nCode: {ev.adjustment_code}"
                    rows.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(ev.date_sold, size=11, color=GREY_TEXT)),
                        ft.DataCell(ft.Text(ev.description, size=11, color=ft.colors.WHITE)),
                        ft.DataCell(ft.Text(ev.term[:2], size=10, color=GREY_TEXT)),
                        ft.DataCell(ft.Text(f"${ev.gain_loss:,.2f}", size=11, color=gc(ev.gain_loss), weight=ft.FontWeight.W_600)),
                        ft.DataCell(ft.Icon(ft.icons.INFO_OUTLINE, size=14, color=GREY_TEXT, tooltip=tooltip_text)),
                    ]))

                def prev_p(e):
                    if page_state["page"] > 1:
                        page_state["page"] -= 1
                        render_table()

                def next_p(e):
                    if page_state["page"] < total_pages:
                        page_state["page"] += 1
                        render_table()

                pagination = ft.Row([
                    ft.IconButton(ft.icons.CHEVRON_LEFT, on_click=prev_p, disabled=page_num <= 1),
                    ft.Text(f"Page {page_num} of {total_pages}  ({total} total)", size=12, color=GREY_TEXT),
                    ft.IconButton(ft.icons.CHEVRON_RIGHT, on_click=next_p, disabled=page_num >= total_pages),
                    ft.Container(expand=True),
                    ft.ElevatedButton("Export CSV", icon=ft.icons.DOWNLOAD,
                        style=ft.ButtonStyle(bgcolor=ft.ControlState.DEFAULT, color=ft.colors.WHITE),
                        on_click=lambda e: export_level3_csv(target, filtered_events)),
                ], spacing=6)

                table_container.content = ft.Column([
                    ft.DataTable(
                        columns=[
                            ft.DataColumn(ft.Text("Date", size=11)),
                            ft.DataColumn(ft.Text("Asset / Description", size=11)),
                            ft.DataColumn(ft.Text("Term", size=11)),
                            ft.DataColumn(ft.Text("Gain / Loss", size=11)),
                            ft.DataColumn(ft.Text("Info", size=11)),
                        ],
                        rows=rows,
                        column_spacing=12,
                        data_row_min_height=34,
                        data_row_max_height=34,
                        heading_row_height=34,
                    ),
                    ft.Container(height=6),
                    pagination,
                ], scroll=ft.ScrollMode.AUTO, spacing=4)

                if table_container.page:
                    table_container.update()

            render_table()

            # ── Totals banner ────────────────────────────────────────────
            total_gain = sum((ev.gain_loss for ev in filtered_events), Decimal("0"))
            st_gain = sum((ev.gain_loss for ev in filtered_events if ev.term == "Short-Term"), Decimal("0"))
            lt_gain = sum((ev.gain_loss for ev in filtered_events if ev.term == "Long-Term"), Decimal("0"))

            main_container.controls.extend([
                ft.Row([
                    ghost_btn("Back to Months", back_fn, ft.icons.ARROW_BACK),
                    ft.Container(expand=True),
                    ft.ElevatedButton("Export CSV", icon=ft.icons.DOWNLOAD,
                        style=ft.ButtonStyle(bgcolor=ft.ControlState.DEFAULT, color=ft.colors.WHITE),
                        on_click=lambda e: export_level3_csv(target, filtered_events)),
                ]),
                ft.Text(f"Detail — {month_label}", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                ft.Container(height=4),
                # ── Summary banner ─────────────────────────────────────
                card(ft.Row([
                    ft.Column([ft.Text("Net", size=10, color=GREY_TEXT), ft.Text(f"${total_gain:,.2f}", size=16, weight=ft.FontWeight.BOLD, color=gc(total_gain))], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                    ft.Container(width=1, height=40, bgcolor=BORDER),
                    ft.Column([ft.Text("Short-Term", size=10, color=GREY_TEXT), ft.Text(f"${st_gain:,.2f}", size=14, color=gc(st_gain))], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                    ft.Container(width=1, height=40, bgcolor=BORDER),
                    ft.Column([ft.Text("Long-Term", size=10, color=GREY_TEXT), ft.Text(f"${lt_gain:,.2f}", size=14, color=gc(lt_gain))], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                    ft.Container(width=1, height=40, bgcolor=BORDER),
                    ft.Column([ft.Text("Transactions", size=10, color=GREY_TEXT), ft.Text(str(len(filtered_events)), size=16, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD)], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                ], spacing=0), bgcolor=BG_CARD, padding=12),
                ft.Container(height=4),
                # ── Daily bar chart ────────────────────────────────────
                card(ft.Column([
                    section_label("DAILY GAIN / LOSS"),
                    ft.Container(height=4),
                    bar_chart_row,
                ]), bgcolor=BG_CARD, padding=12),
                ft.Container(height=4),
                # ── Transaction table ──────────────────────────────────
                card(ft.Column([
                    section_label(f"TRANSACTIONS — {month_label.upper()}"),
                    ft.Container(height=4),
                    table_container,
                ]), bgcolor=BG_CARD, padding=12),
            ])

        # Level 3A (asset transactions) – paginated
        elif lvl == "3A":
            target = view_state["selected_asset"]
            filtered_events = [ev for ev in all_events if target in ev.description.split()]
            def back_fn(e): view_state["level"] = "2A"; refresh_ui()

            page_state_3a = {"page": 1, "per_page": 10}
            table_container_3a = ft.Container(expand=True)

            total_gain_3a = sum((ev.gain_loss for ev in filtered_events), Decimal("0"))
            st_3a = sum((ev.gain_loss for ev in filtered_events if ev.term == "Short-Term"), Decimal("0"))
            lt_3a = sum((ev.gain_loss for ev in filtered_events if ev.term == "Long-Term"), Decimal("0"))

            def render_table_3a():
                page_num = page_state_3a["page"]
                per_page = page_state_3a["per_page"]
                total = len(filtered_events)
                total_pages = max(1, (total + per_page - 1) // per_page)
                start = (page_num - 1) * per_page
                page_events = filtered_events[start: start + per_page]

                rows = []
                for ev in page_events:
                    tooltip_text = f"Proceeds: ${ev.proceeds:,.2f}\nBasis: ${ev.cost_basis:,.2f}\nTerm: {ev.term}"
                    if ev.adjustment_code: tooltip_text += f"\nCode: {ev.adjustment_code}"
                    rows.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(ev.date_sold, size=11, color=GREY_TEXT)),
                        ft.DataCell(ft.Text(ev.description, size=11, color=ft.colors.WHITE)),
                        ft.DataCell(ft.Text(ev.term[:2], size=10, color=GREY_TEXT)),
                        ft.DataCell(ft.Text(f"${ev.gain_loss:,.2f}", size=11, color=gc(ev.gain_loss), weight=ft.FontWeight.W_600)),
                        ft.DataCell(ft.Icon(ft.icons.INFO_OUTLINE, size=14, color=GREY_TEXT, tooltip=tooltip_text)),
                    ]))

                def prev_p(e):
                    if page_state_3a["page"] > 1:
                        page_state_3a["page"] -= 1
                        render_table_3a()

                def next_p(e):
                    if page_state_3a["page"] < total_pages:
                        page_state_3a["page"] += 1
                        render_table_3a()

                pagination = ft.Row([
                    ft.IconButton(ft.icons.CHEVRON_LEFT, on_click=prev_p, disabled=page_num <= 1),
                    ft.Text(f"Page {page_num} of {total_pages}  ({total} total)", size=12, color=GREY_TEXT),
                    ft.IconButton(ft.icons.CHEVRON_RIGHT, on_click=next_p, disabled=page_num >= total_pages),
                ], spacing=6)

                table_container_3a.content = ft.Column([
                    ft.DataTable(
                        columns=[
                            ft.DataColumn(ft.Text("Date", size=11)),
                            ft.DataColumn(ft.Text("Description", size=11)),
                            ft.DataColumn(ft.Text("Term", size=11)),
                            ft.DataColumn(ft.Text("Gain / Loss", size=11)),
                            ft.DataColumn(ft.Text("Info", size=11)),
                        ],
                        rows=rows,
                        column_spacing=12,
                        data_row_min_height=34,
                        data_row_max_height=34,
                        heading_row_height=34,
                    ),
                    ft.Container(height=6),
                    pagination,
                ], spacing=4)
                if table_container_3a.page:
                    table_container_3a.update()

            render_table_3a()

            main_container.controls.extend([
                ft.Row([
                    ghost_btn("Back to Assets", back_fn, ft.icons.ARROW_BACK),
                    ft.Container(expand=True),
                    ft.ElevatedButton("Export CSV", icon=ft.icons.DOWNLOAD,
                        style=ft.ButtonStyle(bgcolor=ft.ControlState.DEFAULT, color=ft.colors.WHITE),
                        on_click=lambda e: export_level3_csv(target, filtered_events)),
                ]),
                ft.Text(f"Transactions — {target}", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                ft.Container(height=4),
                card(ft.Row([
                    ft.Column([ft.Text("Net", size=10, color=GREY_TEXT), ft.Text(f"${total_gain_3a:,.2f}", size=16, weight=ft.FontWeight.BOLD, color=gc(total_gain_3a))], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                    ft.Container(width=1, height=40, bgcolor=BORDER),
                    ft.Column([ft.Text("Short-Term", size=10, color=GREY_TEXT), ft.Text(f"${st_3a:,.2f}", size=14, color=gc(st_3a))], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                    ft.Container(width=1, height=40, bgcolor=BORDER),
                    ft.Column([ft.Text("Long-Term", size=10, color=GREY_TEXT), ft.Text(f"${lt_3a:,.2f}", size=14, color=gc(lt_3a))], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                    ft.Container(width=1, height=40, bgcolor=BORDER),
                    ft.Column([ft.Text("Transactions", size=10, color=GREY_TEXT), ft.Text(str(len(filtered_events)), size=16, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD)], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                ], spacing=0), bgcolor=BG_CARD, padding=12),
                ft.Container(height=4),
                card(ft.Column([
                    section_label(f"TRANSACTIONS — {target}"),
                    ft.Container(height=4),
                    table_container_3a,
                ]), bgcolor=BG_CARD, padding=12),
            ])
            
        def export_level3_csv(label, target_events):
            import csv
            import os
            
            project_root_loc = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            path = os.path.join(project_root_loc, "app", "docs", f"export_{label.replace(' ','_')}.csv")
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Date", "Description", "Proceeds", "Cost Basis", "Gain/Loss", "Term", "Code", "Adjustment"])
                    for ev in target_events:
                        writer.writerow([ev.date_sold, ev.description, ev.proceeds, ev.cost_basis, ev.gain_loss, ev.term, ev.adjustment_code, ev.adjustment_amount])
                page.snack_bar = ft.SnackBar(ft.Text(f"Exported to {path}"), bgcolor=ft.colors.GREEN_800)
                page.snack_bar.open = True
                page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Export Failed: {str(ex)}"), bgcolor=ft.colors.RED_600)
                page.snack_bar.open = True
                page.update()

        # Global Bottom Bar
        if lvl == 1:
            main_container.controls.extend([
                ft.Container(height=10),
                ft.Row([
                    ghost_btn("Back to Config", on_back, ft.icons.ARROW_BACK),
                    ft.Container(expand=True),
                    ft.ElevatedButton(
                        content=ft.Row([ft.Icon(ft.icons.DOWNLOAD, size=16), ft.Text("Download Reports", size=13, weight=ft.FontWeight.W_700)], spacing=6, tight=True),
                        on_click=on_next,
                        style=ft.ButtonStyle(
                            bgcolor=AMBER,
                            color=ft.colors.BLACK,
                            padding=ft.padding.symmetric(horizontal=20, vertical=13),
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                    ),
                ]),
            ])

        if main_container.page:
            main_container.update()

    try:
        refresh_ui()
    except Exception as ex:
        import traceback
        main_container.controls.append(ft.Text(f"ERROR rendering Review Step (6):\n{str(ex)}\n{traceback.format_exc()}", color=ft.colors.RED, selectable=True))
    
    return main_container


# ── STEP 7: DOWNLOAD ──────────────────────────────────────────────────────────
def build_download_step(page: ft.Page, state: WizardState, on_back, on_restart,
                        save_8949, save_tt, save_audit):
    save_log_items = ft.Column([
        ft.Row([
            ft.Icon(ft.icons.INFO_OUTLINE, color=GREY_TEXT, size=16),
            ft.Text("Files you save will appear here.", size=12, color=GREY_TEXT),
        ], spacing=8)
    ], spacing=6)
    save_log = ft.Text("", size=12, color=ft.colors.GREEN_400)  # kept for compat

    def save(picker, content, filename):
        def on_save(ev: ft.FilePickerResultEvent):
            if ev.path:
                newline = "" if filename.endswith(".csv") else None
                with open(ev.path, "w", **({"newline": newline} if newline is not None else {}), encoding="utf-8") as f:
                    f.write(content)
                # Remove placeholder row and add a success row
                if len(save_log_items.controls) == 1 and isinstance(save_log_items.controls[0], ft.Row) and "appear here" in str(getattr(save_log_items.controls[0].controls[1], 'value', '')):
                    save_log_items.controls.clear()
                save_log_items.controls.append(ft.Row([
                    ft.Icon(ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN_400, size=16),
                    ft.Text(f"Saved → {ev.path}", size=12, color=ft.colors.GREEN_400, selectable=True),
                ], spacing=8))
                if save_log_items.page:
                    save_log_items.update()
        picker.on_result = on_save
        ext = "csv" if filename.endswith("csv") else "txt"
        picker.save_file(file_name=filename, allowed_extensions=[ext])

    def make_card(icon, title, subtitle, color, on_click):
        return ft.Container(
            padding=ft.padding.all(16), bgcolor=BG_CARD, border_radius=12,
            border=ft.border.all(1, BORDER),
            content=ft.Row([
                ft.Icon(icon, color=color, size=26),
                ft.Column([
                    ft.Text(title, size=14, weight=ft.FontWeight.W_700, color=ft.colors.WHITE),
                    ft.Text(subtitle, size=11, color=GREY_TEXT),
                ], spacing=2, expand=True),
                ft.ElevatedButton(
                    content=ft.Row([ft.Icon(ft.icons.DOWNLOAD, size=14), ft.Text("Save", size=12)], spacing=4, tight=True),
                    on_click=on_click,
                    style=ft.ButtonStyle(
                        bgcolor=color,
                        color=ft.colors.BLACK,
                        padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    return ft.Column([
        ft.Text("Step 7 — Download Tax Files", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
        ft.Text("Save each report to your preferred location.", size=13, color=GREY_TEXT),
        ft.Container(height=10),
        make_card(ft.icons.DESCRIPTION, "IRS Form 8949",
                  "Capital gains & losses with cost basis",
                  ft.colors.GREEN_400,
                  lambda e: save(save_8949, state.report_data.get("form8949", ""), "form_8949_2025.csv")),
        make_card(ft.icons.TABLE_CHART, "TurboTax Gain/Loss CSV",
                  "Import directly into TurboTax",
                  ft.colors.BLUE_300,
                  lambda e: save(save_tt, state.report_data.get("turbotax", ""), "turbotax_gain_loss_2025.csv")),
        make_card(ft.icons.HISTORY_EDU, "Audit Trail Log",
                  "Complete FIFO trace — keep as IRS backup",
                  ft.colors.PURPLE_300,
                  lambda e: save(save_audit, state.report_data.get("audit", ""), "audit_trail_2025.txt")),
        ft.Container(height=6),
        card(ft.Column([
            section_label("SAVED FILES"),
            ft.Container(height=6),
            save_log_items,
        ]), bgcolor="#060f06", border_color=ft.colors.GREEN_900, padding=14),
        ft.Container(height=10),
        ft.Row([
            ghost_btn("Back to Review", on_back, ft.icons.ARROW_BACK),
            ft.Container(expand=True),
            ghost_btn("Start New Calculation", on_restart, ft.icons.REFRESH),
        ]),
    ], spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)


def main(page: ft.Page):
    page.title = "Crypto Tax Pro 2026"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG_DARK
    page.padding = 0
    page.window.width = 1100
    page.window.height = 840

    state = WizardState()

    input_picker   = ft.FilePicker()
    save_8949_picker = ft.FilePicker()
    save_tt_picker   = ft.FilePicker()
    save_audit_picker = ft.FilePicker()
    for p in [input_picker, save_8949_picker, save_tt_picker, save_audit_picker]:
        page.overlay.append(p)

    def render(step_index, content):
        page.controls.clear()
        if step_index >= 0:
            page.controls.append(build_step_indicator(step_index))
        page.controls.append(
            ft.Container(expand=True, padding=ft.padding.all(32), content=content)
        )
        page.update()

    # Navigation
    def go_eula():       render(-1, build_eula(page, go_step0))
    def go_step0(_=None): render(0, build_exchange_step(page, state, go_step1))
    def go_step1(_=None): render(1, build_file_step(page, state, go_step0, go_step2, input_picker))

    def go_step2(_=None):
        try:
            all_entries = []
            for f in state.uploaded_files:
                if f.get("validation") and f["validation"].status != "error":
                    all_entries.extend(load_ledgers(f["path"], wallet_id=f["wallet"], exchange_key=f.get("exchange_key", "kraken")))
            state.wallet_summary = get_wallet_summary(all_entries)
            # Derive available years from loaded entry timestamps
            years = sorted(set(
                e.time.year for e in all_entries
                if hasattr(e, 'time') and e.time is not None
            ))
            state.available_years = years
            # Auto-select the most recent year as the default period
            if years:
                latest = years[-1]
                state.tax_year    = latest
                state.period_start = datetime.date(latest, 1, 1)
                state.period_end   = datetime.date(latest, 12, 31)
        except Exception:
            state.wallet_summary  = []
            state.available_years = []
        render(2, build_wallet_step(page, state, go_step1, go_step3))

    def go_step3(_=None): render(3, build_config_step(page, state, go_step2, go_step4))
    def show_error_modal(err_msg: str):
        def close_dlg(e):
            err_dlg.open = False
            page.update()
            
        err_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.icons.ERROR_OUTLINE, color=ft.colors.RED_400), ft.Text("Processing Error")], spacing=10),
            content=ft.Column([
                ft.Text("The engine encountered an unexpected error while processing your files:", size=13),
                ft.Container(
                    content=ft.Text(err_msg, size=11, font_family="monospace", color=ft.colors.RED_300, selectable=True),
                    bgcolor="#1a0a0a",
                    padding=10,
                    border_radius=6,
                    border=ft.border.all(1, ft.colors.RED_900),
                    height=200,
                ),
                ft.Text("Suggestion: Verify that your CSV headers match the exact specifications required by the platform, or return to Configuration to reset parameters.", size=12, color=GREY_TEXT)
            ], tight=True, width=500),
            actions=[
                ft.TextButton("Go Back and Retry", on_click=lambda e: (close_dlg(e), go_step3()))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(err_dlg)
        err_dlg.open = True
        page.update()

    def go_step4(_=None): render(4, build_processing_step(page, state, go_step5, show_error_modal, on_back=go_step3))
    def go_step5(_=None): render(5, build_review_step(page, state, go_step3, go_step6))

    def go_step6(_=None):
        render(6, build_download_step(page, state, go_step5, restart,
                                      save_8949_picker, save_tt_picker, save_audit_picker))

    def restart(_=None):
        nonlocal state
        state = WizardState()
        go_eula()

    go_eula()


if __name__ == "__main__":
    ft.app(target=main)
