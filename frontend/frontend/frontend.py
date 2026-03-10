import reflex as rx
import httpx
import json
import os
import logging
import sys
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.main import api as autodevapi

# --- Set up absolute pathing for production ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autodev_deploy")

# =========================
# V3: DEEP SPACE DESIGN SYSTEM
# =========================

STYLE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

body {
    background-color: #020617; /* Slate 950 */
    color: #f8fafc; /* Slate 50 */
    font-family: 'Outfit', sans-serif;
    overflow-x: hidden;
    margin: 0;
    padding: 0;
}

/* Subtle architectural grid */
.bg-grid {
    position: fixed;
    top: 0; left: 0; width: 100vw; height: 100vh;
    background-image: 
        linear-gradient(to right, rgba(255,255,255,0.02) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(255,255,255,0.02) 1px, transparent 1px);
    background-size: 40px 40px;
    z-index: -2;
    mask-image: linear-gradient(to bottom, black 30%, transparent 100%);
    -webkit-mask-image: linear-gradient(to bottom, black 30%, transparent 100%);
}

/* Massive, slow-moving atmospheric glows */
@keyframes drift1 {
    0% { transform: translate(0, 0) scale(1); }
    33% { transform: translate(3%, 4%) scale(1.05); }
    66% { transform: translate(-2%, 2%) scale(0.95); }
    100% { transform: translate(0, 0) scale(1); }
}
@keyframes drift2 {
    0% { transform: translate(0, 0) scale(1.1); }
    33% { transform: translate(-4%, -3%) scale(1); }
    66% { transform: translate(2%, -4%) scale(1.15); }
    100% { transform: translate(0, 0) scale(1.1); }
}

.glow-orb-1 {
    position: fixed; top: -20vh; left: -10vw; width: 70vw; height: 70vw;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.12) 0%, transparent 70%);
    filter: blur(120px); z-index: -1;
    animation: drift1 25s ease-in-out infinite alternate;
}

.glow-orb-2 {
    position: fixed; bottom: -20vh; right: -10vw; width: 70vw; height: 70vw;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(14, 165, 233, 0.12) 0%, transparent 70%);
    filter: blur(120px); z-index: -1;
    animation: drift2 30s ease-in-out infinite alternate;
}

/* Ultra-premium glassmorphism card */
.glass-panel {
    background: rgba(15, 23, 42, 0.6); /* Slate 900 */
    backdrop-filter: blur(32px);
    -webkit-backdrop-filter: blur(32px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 
        0 25px 50px -12px rgba(0, 0, 0, 0.7), 
        inset 0 1px 0 rgba(255, 255, 255, 0.1),
        inset 0 0 20px rgba(255,255,255,0.02);
}

/* Input Overrides for premium feel */
.rt-TextAreaInput, .rt-TextFieldInput {
    background: rgba(30, 41, 59, 0.5) !important; /* Slate 800 */
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: white !important;
    transition: all 0.2s ease;
    font-family: 'Outfit', sans-serif !important;
}
.rt-TextAreaInput:focus, .rt-TextFieldInput:focus {
    border-color: rgba(99, 102, 241, 0.6) !important;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2) !important;
    background: rgba(30, 41, 59, 0.8) !important;
}

/* Magical Gradient Button */
.btn-magic {
    background: linear-gradient(135deg, #6366f1 0%, #0ea5e9 100%);
    color: white !important;
    border: none !important;
    box-shadow: 
        0 4px 14px 0 rgba(99, 102, 241, 0.4),
        inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600 !important;
}
.btn-magic:hover {
    transform: translateY(-2px);
    box-shadow: 
        0 8px 25px -5px rgba(99, 102, 241, 0.6),
        0 4px 10px -3px rgba(14, 165, 233, 0.5),
        inset 0 1px 0 rgba(255, 255, 255, 0.3) !important;
    filter: brightness(1.1);
}
.btn-magic:active {
    transform: translateY(1px);
}

/* Clean IDE Terminal */
.ide-terminal {
    background: rgba(2, 6, 23, 0.8) !important; /* Slate 950 */
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: inset 0 2px 15px rgba(0,0,0,0.8);
    backdrop-filter: blur(10px);
}
.ide-header {
    background: rgba(15, 23, 42, 0.95); /* Slate 900 */
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
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
    """Helper for a beautifully aligned form field with enhanced typography."""
    return rx.vstack(
        rx.text(label, size="2", weight="bold", color="#cbd5e1", letter_spacing="0.02em"),
        rx.text_area(
            placeholder=placeholder,
            value=value_bind,
            on_change=on_change_bind,
            size="3",
            variant="surface",
            min_height="140px" if is_textarea else "auto",
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
    )

def log_terminal() -> rx.Component:
    """The ultra-modern IDE console with macOS-style window controls."""
    return rx.box(
        # Terminal Header
        rx.hstack(
            rx.hstack(
                rx.box(width="12px", height="12px", bg="#ff5f56", border_radius="50%", box_shadow="0 0 4px rgba(255,95,86,0.5)"),
                rx.box(width="12px", height="12px", bg="#ffbd2e", border_radius="50%", box_shadow="0 0 4px rgba(255,189,46,0.5)"),
                rx.box(width="12px", height="12px", bg="#27c93f", border_radius="50%", box_shadow="0 0 4px rgba(39,201,63,0.5)"),
                spacing="3",
            ),
            rx.text("autodev-core-agent ~ zsh", font_family="'JetBrains Mono', monospace", font_size="0.75em", color="#64748b", margin_left="1.5em", weight="medium"),
            padding="12px 20px",
            className="ide-header",
            align_items="center",
            border_top_radius="16px",
        ),
        # Log Scroll Area
        rx.scroll_area(
            rx.vstack(
                rx.foreach(
                    State.logs,
                    lambda log: rx.text(
                        rx.cond(
                            log.contains("[ERROR]"),
                            "🚨 " + log,
                            rx.cond(
                                log.contains("[SUCCESS]"),
                                "✨ " + log,
                                rx.cond(
                                    log.contains("[SYSTEM]"),
                                    "⚡ " + log,
                                    "➜  " + log
                                )
                            )
                        ),
                        font_family="'JetBrains Mono', monospace",
                        font_size="0.85em",
                        color=rx.cond(
                            log.contains("[ERROR]"), 
                            "#fca5a5", # Red for errors
                            rx.cond(
                                log.contains("[SUCCESS]"),
                                "#6ee7b7", # Mint for success
                                rx.cond(
                                    log.contains("[SYSTEM]"),
                                    "#c4b5fd", # Purple for system messages
                                    "#bae6fd"  # Soft blue for standard logs
                                )
                            )
                        ),
                        line_height="1.7",
                        letter_spacing="-0.01em",
                    ),
                ),
                align_items="flex-start",
                width="100%",
                padding="2",
            ),
            height="340px",
            padding="1.5em",
            className="ide-terminal",
            border_bottom_radius="16px",
        ),
        margin_top="2.5em",
        width="100%",
        box_shadow="0 20px 40px -15px rgba(0,0,0,0.5)",
    )

def index():
    return rx.box(
        # Inject CSS
        rx.el.style(STYLE_CSS),
        
        # Background Elements
        rx.box(className="bg-grid"),
        rx.box(className="glow-orb-1"),
        rx.box(className="glow-orb-2"),

        # Main Content Centering
        rx.center(
            rx.box(
                rx.vstack(
                    # Header Elements
                    rx.center(
                        rx.box(
                            rx.icon(tag="bot", size=48, color="#38bdf8"),
                            background="rgba(15, 23, 42, 0.5)",
                            padding="16px",
                            border_radius="24px",
                            border="1px solid rgba(255,255,255,0.05)",
                            box_shadow="inset 0 1px 0 rgba(255,255,255,0.1)",
                            margin_bottom="1em",
                        ),
                        rx.hstack(
                            rx.heading("AutoDev", size="9", weight="bold", color="#f8fafc", letter_spacing="-2px"),
                            rx.heading("AI", size="9", weight="bold", background_image="linear-gradient(135deg, #818cf8 0%, #38bdf8 100%)", background_clip="text", color="transparent", letter_spacing="-2px"),
                            spacing="3",
                            align_items="center",
                        ),
                        rx.text("Autonomous Backend Architect", size="4", color="#94a3b8", weight="medium", margin_top="0.5em", letter_spacing="0.05em", text_transform="uppercase"),
                        direction="column",
                        align_items="center",
                        width="100%",
                        margin_bottom="2em",
                    ),

                    rx.divider(opacity="0.1", margin_bottom="2.5em"),

                    # Input Form uses a cleaner flex layout for better responsiveness
                    rx.vstack(
                        rx.hstack(
                            rx.box(form_field("Project Name", "e.g. intelligent-api", State.project_name, State.set_project_name), width="50%"),
                            rx.box(form_field("Tech Stack Constraints", "e.g. Python, FastAPI, Postgres", State.tech_stack_input, State.set_tech_stack_input), width="50%"),
                            spacing="5",
                            width="100%",
                        ),
                        rx.box(
                            form_field("Architecture Description", "Describe your endpoints, database schemas, and business logic here in detail...", State.description, State.set_description, is_textarea=True),
                            width="100%"
                        ),
                        spacing="6",
                        width="100%",
                    ),

                    # Action Button
                    rx.box(margin_y="1em", width="100%"),
                    rx.button(
                        rx.icon(tag="cpu", size=20, margin_right="3"),
                        "INITIALIZE SYSTEM BUILD",
                        on_click=State.start_build,
                        loading=State.is_building,
                        width="100%",
                        size="4",
                        className="btn-magic",
                        border_radius="12px",
                        padding="28px",
                    ),

                    # Download Button (Conditional)
                    rx.cond(
                        State.download_url != "",
                        rx.box(
                            rx.link(
                                rx.button(
                                    rx.icon(tag="download", size=20, margin_right="3"),
                                    "DOWNLOAD SOURCE ARCHIVE",
                                    width="100%",
                                    size="4",
                                    color_scheme="jade",
                                    variant="solid",
                                    border_radius="12px",
                                    padding="28px",
                                    box_shadow="0 4px 14px 0 rgba(16, 185, 129, 0.39)",
                                ),
                                href=State.download_url,
                                is_external=True,
                            ),
                            margin_top="1.5em",
                            width="100%",
                        ),
                    ),

                    # Terminal Output (Conditional)
                    rx.cond(
                        State.logs,
                        log_terminal(),
                    ),

                    spacing="0",
                    width="100%",
                ),
                width=["95%", "900px"],
                padding=["2em", "4em"],
                border_radius="32px",
                className="glass-panel",
                margin_y="5em",
            ),
            min_height="100vh",
            width="100vw",
        ),
    )

# =========================
# APP CONFIGURATION
# =========================

def mount_autodev(app: FastAPI) -> FastAPI:
    app.mount("/autodev", autodevapi)

    if os.path.exists("public"):
        app.mount("/", StaticFiles(directory="public", html=True), name="static")
    
    async def caught_all(request: Request):
        rest_of_path = request.path_params.get("rest_of_path", "")
        if not rest_of_path.startswith("autodev") and os.path.exists("public/index.html"):
            return FileResponse("public/index.html")
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    app.add_route("/{rest_of_path:path}", caught_all, methods=["GET"])
    return app

app = rx.App(
    theme=rx.theme(
        appearance="dark", 
        has_background=False, # We are providing our own background
        radius="medium",
        accent_color="indigo"
    ),
    api_transformer=mount_autodev,
)

app.add_page(index, title="AutoDev AI | System Architect", on_load=State.reset_state)