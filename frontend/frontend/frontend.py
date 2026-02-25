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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

body {
    background-color: #030712;
    color: #f9fafb;
    font-family: 'Inter', sans-serif;
    overflow-x: hidden;
}

/* Subtle architectural grid */
.bg-grid {
    position: fixed;
    top: 0; left: 0; width: 100vw; height: 100vh;
    background-image: 
        linear-gradient(to right, rgba(255,255,255,0.03) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(255,255,255,0.03) 1px, transparent 1px);
    background-size: 50px 50px;
    z-index: -2;
    mask-image: linear-gradient(to bottom, white 20%, transparent 100%);
    -webkit-mask-image: linear-gradient(to bottom, white 20%, transparent 100%);
}

/* Massive, slow-moving atmospheric glows */
@keyframes drift1 {
    0% { transform: translate(0, 0) scale(1); }
    50% { transform: translate(5%, 5%) scale(1.1); }
    100% { transform: translate(0, 0) scale(1); }
}
@keyframes drift2 {
    0% { transform: translate(0, 0) scale(1.1); }
    50% { transform: translate(-5%, -5%) scale(1); }
    100% { transform: translate(0, 0) scale(1.1); }
}

.glow-orb-1 {
    position: fixed; top: -10vh; left: -10vw; width: 60vw; height: 60vw;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 60%);
    filter: blur(100px); z-index: -1;
    animation: drift1 20s ease-in-out infinite;
}

.glow-orb-2 {
    position: fixed; bottom: -10vh; right: -10vw; width: 60vw; height: 60vw;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(14, 165, 233, 0.15) 0%, transparent 60%);
    filter: blur(100px); z-index: -1;
    animation: drift2 25s ease-in-out infinite;
}

/* Ultra-premium glassmorphism */
.glass-panel {
    background: rgba(15, 23, 42, 0.4);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

/* Magical Gradient Button */
.btn-magic {
    background: linear-gradient(135deg, #4f46e5 0%, #0ea5e9 100%);
    color: white;
    box-shadow: 0 4px 14px 0 rgba(79, 70, 229, 0.39);
    transition: all 0.3s ease;
}
.btn-magic:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(79, 70, 229, 0.6);
}

/* Clean IDE Terminal */
.ide-terminal {
    background: #0b0f19;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);
}
.ide-header {
    background: #111827;
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
    """Helper for a beautifully aligned form field."""
    return rx.vstack(
        rx.text(label, size="2", weight="medium", color="#94a3b8"),
        rx.text_area(
            placeholder=placeholder,
            value=value_bind,
            on_change=on_change_bind,
            size="3",
            variant="surface",
            min_height="120px" if is_textarea else "auto",
            width="100%",
            radius="medium",
        ) if is_textarea else rx.input(
            placeholder=placeholder,
            value=value_bind,
            on_change=on_change_bind,
            size="3",
            variant="surface",
            width="100%",
            radius="medium",
        ),
        width="100%",
        spacing="2",
    )

def log_terminal() -> rx.Component:
    """The ultra-modern IDE console."""
    return rx.box(
        # Terminal Header
        rx.hstack(
            rx.hstack(
                rx.box(width="10px", height="10px", bg="#ef4444", border_radius="50%"),
                rx.box(width="10px", height="10px", bg="#eab308", border_radius="50%"),
                rx.box(width="10px", height="10px", bg="#22c55e", border_radius="50%"),
                spacing="2",
            ),
            rx.text("AutoDev Core Agent Output", font_family="'Inter', sans-serif", font_size="0.75em", color="#64748b", margin_left="1em", weight="medium"),
            padding="10px 16px",
            className="ide-header",
            align_items="center",
            border_top_radius="12px",
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
                                "➜  " + log
                            )
                        ),
                        font_family="'JetBrains Mono', monospace",
                        font_size="0.8em",
                        color=rx.cond(
                            log.contains("[ERROR]"), 
                            "#fca5a5", # Red for errors
                            rx.cond(
                                log.contains("[SUCCESS]"),
                                "#6ee7b7", # Mint for success
                                "#93c5fd"  # Soft blue for standard logs
                            )
                        ),
                        line_height="1.6",
                    ),
                ),
                align_items="flex-start",
                width="100%",
                padding="2",
            ),
            height="320px",
            padding="1em",
            className="ide-terminal",
            border_bottom_radius="12px",
        ),
        margin_top="2em",
        width="100%",
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
                        rx.icon(tag="bot", size=42, color="#0ea5e9", margin_bottom="0.5em"),
                        rx.hstack(
                            rx.heading("AutoDev", size="9", weight="bold", color="#f8fafc", letter_spacing="-1px"),
                            rx.heading("AI", size="9", weight="bold", background_image="linear-gradient(135deg, #818cf8 0%, #38bdf8 100%)", background_clip="text", color="transparent", letter_spacing="-1px"),
                            spacing="2",
                            align_items="center",
                        ),
                        rx.text("Autonomous Backend Architect", size="4", color="#94a3b8", weight="medium", margin_top="0.2em"),
                        direction="column",
                        align_items="center",
                        width="100%",
                        margin_bottom="1.5em",
                    ),

                    rx.divider(opacity="0.1", margin_bottom="2em"),

                    # Input Form
                    rx.vstack(
                        rx.hstack(
                            rx.box(form_field("Project Name", "e.g. smart-todo-api", State.project_name, State.set_project_name), width="50%"),
                            rx.box(form_field("Tech Stack Constraints", "e.g. Python, FastAPI, SQLite", State.tech_stack_input, State.set_tech_stack_input), width="50%"),
                            spacing="4",
                            width="100%",
                        ),
                        form_field("Architecture Description", "Describe your endpoints, database schemas, and business logic here...", State.description, State.set_description, is_textarea=True),
                        spacing="5",
                        width="100%",
                    ),

                    # Action Button
                    rx.box(margin_y="0.5em"),
                    rx.button(
                        rx.icon(tag="cpu", size=18, margin_right="2"),
                        "INITIALIZE SYSTEM BUILD",
                        on_click=State.start_build,
                        loading=State.is_building,
                        width="100%",
                        size="4",
                        className="btn-magic",
                        border_radius="8px",
                    ),

                    # Download Button (Conditional)
                    rx.cond(
                        State.download_url != "",
                        rx.box(
                            rx.link(
                                rx.button(
                                    rx.icon(tag="download", size=18, margin_right="2"),
                                    "DOWNLOAD SOURCE ARCHIVE",
                                    width="100%",
                                    size="4",
                                    color_scheme="jade",
                                    variant="solid",
                                    border_radius="8px",
                                ),
                                href=State.download_url,
                                is_external=True,
                            ),
                            margin_top="1em",
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
                width=["95%", "850px"],
                padding=["2em", "3.5em"],
                border_radius="24px",
                className="glass-panel",
                margin_y="4em",
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