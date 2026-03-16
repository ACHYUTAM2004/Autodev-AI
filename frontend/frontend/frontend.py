import os
import sys

# --- MUST be first: add project root to path so 'app' module is found ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import reflex as rx
import httpx
import json
import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.main import api as autodevapi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autodev_deploy")

# =========================
# PREMIUM GLASS UI DESIGN SYSTEM
# =========================

STYLE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

*, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

:root {
    --indigo: #6366f1;
    --sky: #0ea5e9;
    --violet: #8b5cf6;
    --glass-bg: rgba(12, 20, 40, 0.72);
    --glass-border: rgba(255, 255, 255, 0.07);
    --glass-light: rgba(255, 255, 255, 0.03);
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #475569;
    --accent: #6366f1;
}

html, body {
    min-height: 100vh;
    width: 100%;
    background: #050a18;
    color: var(--text-primary);
    font-family: 'Inter', -apple-system, sans-serif;
    overflow-x: hidden;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* =================== BACKGROUND =================== */
.anim-bg {
    position: fixed;
    inset: 0;
    z-index: 0;
    overflow: hidden;
    pointer-events: none;
}

.anim-bg::before {
    content: '';
    position: absolute;
    top: -20%;
    left: -15%;
    width: 70vw;
    height: 70vw;
    background: radial-gradient(ellipse, rgba(99, 102, 241, 0.45) 0%, rgba(99, 102, 241, 0.12) 45%, transparent 70%);
    animation: orb1 20s ease-in-out infinite alternate;
    border-radius: 50%;
    filter: blur(40px);
}

.anim-bg::after {
    content: '';
    position: absolute;
    bottom: -20%;
    right: -15%;
    width: 65vw;
    height: 65vw;
    background: radial-gradient(ellipse, rgba(14, 165, 233, 0.4) 0%, rgba(14, 165, 233, 0.1) 45%, transparent 70%);
    animation: orb2 25s ease-in-out infinite alternate;
    border-radius: 50%;
    filter: blur(40px);
}

.anim-orb3 {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 55vw;
    height: 55vw;
    background: radial-gradient(ellipse, rgba(139, 92, 246, 0.25) 0%, rgba(139, 92, 246, 0.06) 50%, transparent 75%);
    border-radius: 50%;
    filter: blur(50px);
    animation: orb3 30s ease-in-out infinite alternate;
}

@keyframes orb1 {
    0%   { transform: translate(0, 0) scale(1); }
    50%  { transform: translate(5%, 8%) scale(1.1); }
    100% { transform: translate(-3%, 5%) scale(0.95); }
}
@keyframes orb2 {
    0%   { transform: translate(0, 0) scale(1.1); }
    50%  { transform: translate(-6%, -5%) scale(1); }
    100% { transform: translate(4%, -8%) scale(1.15); }
}
@keyframes orb3 {
    0%   { transform: translate(-50%, -50%) scale(1); opacity: 0.8; }
    100% { transform: translate(-50%, -50%) scale(1.3); opacity: 0.4; }
}

.bg-noise {
    position: fixed;
    inset: 0;
    z-index: 1;
    pointer-events: none;
    opacity: 0.025;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    background-repeat: repeat;
    background-size: 128px 128px;
}

/* =================== GRID LINES =================== */
.bg-grid {
    position: fixed;
    inset: 0;
    z-index: 1;
    pointer-events: none;
    background-image:
        linear-gradient(to right, rgba(255,255,255,0.025) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(255,255,255,0.025) 1px, transparent 1px);
    background-size: 56px 56px;
    mask-image: radial-gradient(ellipse 80% 80% at 50% 50%, black 20%, transparent 100%);
    -webkit-mask-image: radial-gradient(ellipse 80% 80% at 50% 50%, black 20%, transparent 100%);
}

/* =================== LAYOUT =================== */
.page-wrapper {
    position: relative;
    z-index: 10;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
}

/* =================== GLASS CARD =================== */
.glass-card {
    width: 100%;
    max-width: 880px;
    background: linear-gradient(
        135deg,
        rgba(20, 30, 60, 0.82) 0%,
        rgba(12, 18, 40, 0.88) 50%,
        rgba(18, 26, 55, 0.82) 100%
    );
    backdrop-filter: blur(48px) saturate(180%);
    -webkit-backdrop-filter: blur(48px) saturate(180%);
    border-radius: 32px;
    border: 1px solid rgba(120, 130, 255, 0.22);
    box-shadow:
        0 0 0 1px rgba(255, 255, 255, 0.04) inset,
        0 4px 6px -1px rgba(0,0,0,0.5),
        0 32px 64px -8px rgba(0,0,0,0.8),
        0 0 80px rgba(99, 102, 241, 0.08);
    padding: 56px 64px;
    position: relative;
    overflow: hidden;
}

.glass-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent 0%, rgba(130, 140, 255, 0.6) 35%, rgba(56, 189, 248, 0.5) 65%, transparent 100%);
}

.glass-card::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent 20%, rgba(99, 102, 241, 0.15) 50%, transparent 80%);
}

@media (max-width: 768px) {
    .glass-card {
        padding: 36px 28px;
        border-radius: 24px;
    }
}

/* =================== HEADER =================== */
.header-icon-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 72px;
    height: 72px;
    border-radius: 22px;
    background: linear-gradient(135deg, rgba(99,102,241,0.25) 0%, rgba(14,165,233,0.15) 100%);
    border: 1px solid rgba(99,102,241,0.3);
    box-shadow:
        0 0 0 1px rgba(255,255,255,0.04) inset,
        0 8px 24px rgba(99,102,241,0.2);
    margin: 0 auto 24px;
    animation: float-icon 5s ease-in-out infinite;
}

@keyframes float-icon {
    0%, 100% { transform: translateY(0px); box-shadow: 0 0 0 1px rgba(255,255,255,0.04) inset, 0 8px 24px rgba(99,102,241,0.2); }
    50%       { transform: translateY(-8px); box-shadow: 0 0 0 1px rgba(255,255,255,0.04) inset, 0 20px 40px rgba(99,102,241,0.3); }
}

.header-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 14px;
    border-radius: 100px;
    background: rgba(99,102,241,0.12);
    border: 1px solid rgba(99,102,241,0.25);
    color: #a5b4fc;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 16px;
}

.header-title {
    font-size: clamp(2.5rem, 5vw, 3.8rem);
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1;
    text-align: center;
    margin-bottom: 12px;
    background: linear-gradient(135deg, #f1f5f9 0%, #cbd5e1 40%, #818cf8 70%, #38bdf8 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}

.header-subtitle {
    font-size: 15px;
    font-weight: 400;
    color: var(--text-secondary);
    letter-spacing: 0.01em;
    text-transform: none;
    text-align: center;
    margin-bottom: 0;
    line-height: 1.6;
}

/* =================== DIVIDER =================== */
.glass-divider {
    width: 100%;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--glass-border), transparent);
    margin: 40px 0;
}

/* =================== FORM FIELDS =================== */
.field-label {
    font-size: 11.5px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-secondary);
    margin-bottom: 8px;
    display: block;
}

/* Target ALL Radix input/textarea variants for reliable production rendering */
.rt-TextFieldRoot, .rt-TextFieldInput,
.rt-TextAreaRoot {
    width: 100% !important;
    box-sizing: border-box !important;
}

.rt-TextFieldInput, .rt-TextAreaInput {
    background: rgba(255, 255, 255, 0.04) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 12px !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
    transition: border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease !important;
    padding: 12px 16px !important;
    width: 100% !important;
    box-sizing: border-box !important;
}

/* Ensure textarea minimum height is enforced at multiple levels */
.rt-TextAreaRoot,
.rt-TextAreaRoot > .rt-ScrollAreaRoot,
.rt-TextAreaRoot > .rt-ScrollAreaRoot > .rt-ScrollAreaViewport {
    min-height: 150px !important;
    height: auto !important;
}

.rt-TextAreaInput {
    min-height: 150px !important;
    resize: vertical !important;
}

.rt-TextFieldInput:hover, .rt-TextAreaInput:hover {
    border-color: rgba(255,255,255,0.14) !important;
    background: rgba(255, 255, 255, 0.06) !important;
}
.rt-TextFieldInput:focus, .rt-TextAreaInput:focus {
    border-color: rgba(99, 102, 241, 0.5) !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12), 0 4px 12px rgba(0,0,0,0.2) !important;
    background: rgba(99, 102, 241, 0.05) !important;
    outline: none !important;
}

/* =================== BUTTON =================== */
.btn-build {
    position: relative;
    width: 100%;
    padding: 18px 32px !important;
    border-radius: 14px !important;
    border: none !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    cursor: pointer;
    overflow: hidden;
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 40%, #7c3aed 100%) !important;
    color: white !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.15) inset,
        0 8px 20px rgba(99, 102, 241, 0.35),
        0 24px 48px rgba(99, 102, 241, 0.15) !important;
    transition: transform 0.2s ease, box-shadow 0.25s ease, filter 0.15s ease !important;
}
.btn-build::before {
    content: '';
    position: absolute;
    top: 0; left: -100%;
    width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
    transition: left 0.5s ease;
}
.btn-build:hover {
    transform: translateY(-2px) !important;
    filter: brightness(1.1) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.2) inset,
        0 12px 32px rgba(99, 102, 241, 0.5),
        0 32px 56px rgba(99, 102, 241, 0.2) !important;
}
.btn-build:hover::before { left: 100%; }
.btn-build:active { transform: translateY(0px) !important; filter: brightness(0.95) !important; }

.btn-download {
    position: relative;
    width: 100%;
    padding: 18px 32px !important;
    border-radius: 14px !important;
    border: 1px solid rgba(16, 185, 129, 0.3) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    background: linear-gradient(135deg, rgba(16,185,129,0.2) 0%, rgba(5,150,105,0.25) 100%) !important;
    color: #34d399 !important;
    box-shadow: 0 8px 24px rgba(16,185,129,0.15) !important;
    transition: transform 0.2s ease, box-shadow 0.25s ease, filter 0.15s ease !important;
}
.btn-download:hover {
    transform: translateY(-2px) !important;
    filter: brightness(1.1) !important;
    box-shadow: 0 16px 40px rgba(16, 185, 129, 0.3) !important;
}

/* =================== TERMINAL =================== */
.terminal-wrap {
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.07);
    box-shadow: 0 20px 48px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04);
    margin-top: 36px;
}

.terminal-header {
    background: rgba(15, 23, 42, 0.9);
    border-bottom: 1px solid rgba(255,255,255,0.05);
    padding: 14px 20px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.dot-red   { width: 12px; height: 12px; border-radius: 50%; background: #ff5f56; box-shadow: 0 0 6px rgba(255,95,86,0.6); }
.dot-yellow{ width: 12px; height: 12px; border-radius: 50%; background: #ffbd2e; box-shadow: 0 0 6px rgba(255,189,46,0.6); }
.dot-green { width: 12px; height: 12px; border-radius: 50%; background: #27c93f; box-shadow: 0 0 6px rgba(39,201,63,0.6); }

.terminal-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    color: #475569;
    margin-left: 12px;
    letter-spacing: 0.05em;
}

.terminal-body {
    background: rgba(2, 6, 23, 0.85) !important;
    padding: 20px 24px !important;
    min-height: 260px;
    max-height: 380px;
    overflow-y: auto;
    backdrop-filter: blur(10px);
}

.log-line-error   { color: #f87171 !important; }
.log-line-success { color: #4ade80 !important; }
.log-line-system  { color: #c4b5fd !important; }
.log-line-default { color: #7dd3fc !important; }
"""

# =========================
# STATE (Functionally unchanged)
# =========================

class State(rx.State):
    project_name: str = ""
    description: str = ""
    tech_stack_input: str = ""
    is_building: bool = False
    build_result: dict = {}
    logs: list[str] = []
    download_url: str = ""

    def reset_state(self):
        self.project_name = ""
        self.description = ""
        self.tech_stack_input = ""
        self.is_building = False
        self.build_result = {}
        self.logs = []
        self.download_url = ""

    def set_project_name(self, value: str):
        self.project_name = value

    def set_description(self, value: str):
        self.description = value

    def set_tech_stack_input(self, value: str):
        self.tech_stack_input = value

    async def start_build(self):
        if not self.project_name or not self.description:
            return

        self.is_building = True
        self.logs = [f"[SYSTEM] Connecting to AutoDev Agentic Core..."]
        self.logs.append(f"[SYSTEM] Initializing build sequence for '{self.project_name}'...")
        self.download_url = ""
        yield

        payload = {
            "project_name": self.project_name,
            "description": self.description,
            "constraints": {"backend": self.tech_stack_input},
        }

        domain = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")

        try:
            async with httpx.AsyncClient(base_url=domain, timeout=None) as client:
                async with client.stream("POST", "/autodev/build", json=payload) as response:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if data["type"] == "log":
                                self.logs.append(data["content"])
                                yield
                            elif data["type"] == "result":
                                raw_url = data["data"]["download_url"]
                                if "download/" in raw_url:
                                    path = raw_url.split("download/")[-1]
                                    self.download_url = f"/autodev/download/{path}"
                                else:
                                    self.download_url = raw_url
                                self.logs.append("[SUCCESS] Architecture compiled and packaged successfully.")
                                yield
                        except:
                            continue
        except Exception as e:
            self.logs.append(f"[ERROR] Agent synchronization lost: {str(e)}")

        self.is_building = False

# =========================
# UI COMPONENTS
# =========================

def form_field(label: str, placeholder: str, value_bind, on_change_bind, is_textarea: bool = False) -> rx.Component:
    return rx.vstack(
        rx.el.span(label, class_name="field-label"),
        rx.text_area(
            placeholder=placeholder,
            value=value_bind,
            on_change=on_change_bind,
            size="3",
            variant="surface",
            min_height="148px",
            width="100%",
            radius="large",
        ) if is_textarea else rx.input(
            placeholder=placeholder,
            value=value_bind,
            on_change=on_change_bind,
            size="3",
            variant="surface",
            width="100%",
            radius="large",
        ),
        width="100%",
        spacing="2",
        align_items="flex-start",
    )


def log_terminal() -> rx.Component:
    return rx.box(
        # Header bar
        rx.el.div(
            rx.el.div(class_name="dot-red"),
            rx.el.div(class_name="dot-yellow"),
            rx.el.div(class_name="dot-green"),
            rx.el.span("autodev-core  ~  agent-stream", class_name="terminal-title"),
            class_name="terminal-header",
        ),
        # Log body
        rx.scroll_area(
            rx.vstack(
                rx.foreach(
                    State.logs,
                    lambda log: rx.text(
                        rx.cond(
                            log.contains("[ERROR]"),
                            "🚨  " + log,
                            rx.cond(
                                log.contains("[SUCCESS]"),
                                "✅  " + log,
                                rx.cond(
                                    log.contains("[SYSTEM]"),
                                    "⚡  " + log,
                                    "›  " + log
                                )
                            )
                        ),
                        font_family="'JetBrains Mono', monospace",
                        font_size="12.5px",
                        color=rx.cond(
                            log.contains("[ERROR]"), "#f87171",
                            rx.cond(
                                log.contains("[SUCCESS]"), "#4ade80",
                                rx.cond(
                                    log.contains("[SYSTEM]"), "#c4b5fd",
                                    "#7dd3fc"
                                )
                            )
                        ),
                        line_height="1.9",
                        white_space="pre-wrap",
                        word_break="break-all",
                    ),
                ),
                align_items="flex-start",
                width="100%",
                spacing="0",
            ),
            type="auto",
            class_name="terminal-body",
        ),
        class_name="terminal-wrap",
        width="100%",
    )


def index():
    return rx.box(
        # Inject CSS
        rx.el.style(STYLE_CSS),

        # Animated background
        rx.el.div(
            rx.el.div(class_name="anim-orb3"),
            class_name="anim-bg",
        ),
        rx.el.div(class_name="bg-noise"),
        rx.el.div(class_name="bg-grid"),

        # Page wrapper — horizontally & vertically centered
        rx.el.div(
            rx.el.div(
                # ── Header ──────────────────────────────────
                rx.el.div(
                    rx.el.div(
                        rx.icon(tag="bot", size=36, color="#818cf8"),
                        class_name="header-icon-wrapper",
                    ),
                    rx.el.div("✦  Autonomous Backend Architect  ✦", class_name="header-badge"),
                    rx.el.h1("AutoDev AI", class_name="header-title"),
                    rx.el.p(
                        "Describe your architecture. We'll build it.",
                        class_name="header-subtitle",
                        style={"font_size": "15px", "color": "var(--text-secondary)", "text_align": "center", "margin_top": "6px"},
                    ),
                    style={
                        "display": "flex",
                        "flex_direction": "column",
                        "align_items": "center",
                        "width": "100%",
                        "margin_bottom": "40px",
                        "gap": "0",
                    },
                ),

                # ── Divider ──────────────────────────────────
                rx.el.div(class_name="glass-divider"),

                # ── Form ────────────────────────────────────
                rx.el.div(
                    # Row 1: two-column inputs
                    rx.el.div(
                        form_field("Project Name", "e.g.  intelligent-api", State.project_name, State.set_project_name),
                        form_field("Tech Stack", "e.g.  FastAPI · PostgreSQL · Redis", State.tech_stack_input, State.set_tech_stack_input),
                        style={
                            "display": "flex",
                            "flex_direction": "row",
                            "gap": "20px",
                            "width": "100%",
                        },
                    ),
                    # Row 2: full-width textarea
                    form_field(
                        "Architecture Description",
                        "Describe your endpoints, database schemas, auth strategy, and business logic...",
                        State.description,
                        State.set_description,
                        is_textarea=True,
                    ),
                    style={
                        "display": "flex",
                        "flex_direction": "column",
                        "gap": "20px",
                        "width": "100%",
                    },
                ),

                # ── Build Button ─────────────────────────────
                rx.box(height="32px"),
                rx.button(
                    rx.icon(tag="zap", size=18, style={"margin_right": "10px"}),
                    "Initialize System Build",
                    on_click=State.start_build,
                    loading=State.is_building,
                    width="100%",
                    class_name="btn-build",
                ),

                # ── Download Button (conditional) ─────────────
                rx.cond(
                    State.download_url != "",
                    rx.box(
                        rx.box(height="16px"),
                        rx.link(
                            rx.button(
                                rx.icon(tag="download", size=18, style={"margin_right": "10px"}),
                                "Download Source Archive",
                                width="100%",
                                class_name="btn-download",
                            ),
                            href=State.download_url,
                            is_external=True,
                        ),
                        width="100%",
                    ),
                ),

                # ── Terminal (conditional) ────────────────────
                rx.cond(
                    State.logs,
                    log_terminal(),
                ),

                class_name="glass-card",
            ),
            class_name="page-wrapper",
        ),
    )

# =========================
# APP CONFIGURATION
# =========================

def mount_autodev(app: FastAPI) -> FastAPI:
    app.mount("/autodev", autodevapi)

    static_dir = "public"
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    async def caught_all(request: Request):
        path = request.url.path
        if path.startswith("/autodev") or path.startswith("/_") or path.startswith("/static"):
            return JSONResponse({"detail": f"Path {path} not found"}, status_code=404)
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return JSONResponse({"detail": "Frontend not built yet."}, status_code=404)

    app.add_route("/{rest_of_path:path}", caught_all, methods=["GET"])
    return app

app = rx.App(
    theme=rx.theme(
        appearance="dark",
        has_background=False,
        radius="medium",
        accent_color="indigo",
    ),
    api_transformer=mount_autodev,
    stylesheets=[],
)

app.add_page(index, title="AutoDev AI — Autonomous Backend Architect", on_load=State.reset_state)