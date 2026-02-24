import reflex as rx
import httpx
import json
import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Import your backend API
from app.main import api as autodevapi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autodev_deploy")

# =========================
# 1️⃣ PREMIUM CSS SYSTEM
# =========================

STYLE_CSS = """
@keyframes mesh-gradient {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

@keyframes float {
    0% { transform: translateY(0px); }
    50% { transform: translateY(-8px); }
    100% { transform: translateY(0px); }
}

@keyframes pulse-glow {
    0% { box-shadow: 0 0 10px rgba(255,0,150,0.2); }
    50% { box-shadow: 0 0 40px rgba(255,0,200,0.5); }
    100% { box-shadow: 0 0 10px rgba(255,0,150,0.2); }
}

@keyframes scanline {
    0% { transform: translateY(-100%); }
    100% { transform: translateY(100%); }
}

body {
    background: #0b0f19;
}

.mesh-bg {
    background: linear-gradient(-45deg, #0f0c29, #302b63, #1e3a8a, #3b0764);
    background-size: 400% 400%;
    animation: mesh-gradient 20s ease infinite;
}

.glass-card {
    backdrop-filter: blur(35px) saturate(200%);
    -webkit-backdrop-filter: blur(35px) saturate(200%);
    background: linear-gradient(
        145deg,
        rgba(18,18,28,0.9),
        rgba(10,10,20,0.9)
    );
    border: 1px solid rgba(255,255,255,0.08);
    position: relative;
    overflow: hidden;
}

.glass-card::before {
    content: "";
    position: absolute;
    inset: 0;
    background: radial-gradient(
        circle at top left,
        rgba(255,0,150,0.08),
        transparent 50%
    );
    pointer-events: none;
}

.button-glow {
    animation: pulse-glow 3s infinite ease-in-out;
}

.button-glow:hover {
    transform: translateY(-3px) scale(1.02);
    box-shadow: 0 0 50px rgba(255,0,200,0.6);
    transition: all 0.3s ease;
}

.terminal-scan::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(
        to bottom,
        transparent,
        rgba(255,255,255,0.03),
        transparent
    );
    animation: scanline 5s linear infinite;
    pointer-events: none;
}
"""

# =========================
# 2️⃣ STATE (UNCHANGED LOGIC)
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
        self.logs = [f"🚀 Initializing build sequence for '{self.project_name}'..."]
        self.download_url = ""
        yield

        payload = {
            "project_name": self.project_name,
            "description": self.description,
            "constraints": {"backend": self.tech_stack_input},
        }

        domain = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
        logger.info(f"🔗 Connecting to Backend at: {domain}")

        try:
            async with httpx.AsyncClient(base_url=domain, timeout=None) as client:
                async with client.stream("POST", "/autodev/build", json=payload) as response:
                    if response.status_code != 200:
                        self.logs.append(f"❌ Server Error: {response.status_code}")
                        yield
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if data["type"] == "log":
                                self.logs.append(data["content"])
                                yield
                            elif data["type"] == "result":
                                self.build_result = data["data"]
                                raw_url = data["data"]["download_url"]
                                if "download/" in raw_url:
                                    path = raw_url.split("download/")[-1]
                                    self.download_url = f"/autodev/download/{path}"
                                else:
                                    self.download_url = raw_url
                                self.logs.append("✨ Build Sequence Complete!")
                                yield
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            self.logs.append(f"❌ Critical Failure: {str(e)}")
            logger.error(f"❌ CRITICAL ERROR: {e}")

        self.is_building = False

# =========================
# 3️⃣ UI COMPONENTS
# =========================

def progress_section():
    return rx.cond(
        State.is_building,
        rx.box(
            rx.vstack(
                rx.text("Build Progress", size="2", color="gray"),
                rx.progress(value=60, width="100%", size="3", color_scheme="ruby"),
                rx.hstack(
                    rx.badge("Planning"),
                    rx.badge("Generating"),
                    rx.badge("Packaging"),
                    rx.badge("Ready"),
                    spacing="3",
                ),
                spacing="2",
                width="100%",
            ),
            margin_top="1.5em",
        ),
    )

def terminal_window():
    return rx.cond(
        State.logs,
        rx.box(
            rx.vstack(
                rx.text("Live Build Console", color="gray", size="2"),
                rx.scroll_area(
                    rx.vstack(
                        rx.foreach(
                            State.logs,
                            lambda log: rx.text(
                                log,
                                font_family="'JetBrains Mono', monospace",
                                font_size="0.85em",
                                color="#c9d1d9",
                            ),
                        ),
                        align_items="start",
                        spacing="1",
                    ),
                    height="260px",
                ),
                spacing="2",
            ),
            bg="linear-gradient(180deg, #0d1117, #0a0f14)",
            padding="1.2em",
            border_radius="16px",
            border="1px solid rgba(255,255,255,0.08)",
            position="relative",
            className="terminal-scan",
            margin_top="2em",
        ),
    )

def main_card():
    return rx.box(
        rx.vstack(
            rx.heading(
                "AutoDev AI",
                size="9",
                weight="bold",
                background_image="linear-gradient(90deg,#ff006e,#8338ec,#3a86ff)",
                background_clip="text",
                color="transparent",
            ),
            rx.text(
                "Autonomous Backend System Architect",
                color="#8b949e",
            ),

            rx.divider(),

            rx.input(
                placeholder="Project Name",
                value=State.project_name,
                on_change=State.set_project_name,
                size="3",
                radius="large",
            ),

            rx.input(
                placeholder="Preferred Tech Stack",
                value=State.tech_stack_input,
                on_change=State.set_tech_stack_input,
                size="3",
                radius="large",
            ),

            rx.text_area(
                placeholder="Describe what you want to build...",
                value=State.description,
                on_change=State.set_description,
                min_height="140px",
                radius="large",
            ),

            rx.button(
                "Synthesize System",
                on_click=State.start_build,
                loading=State.is_building,
                size="4",
                width="100%",
                className="button-glow",
                background="linear-gradient(90deg,#ff006e,#8338ec,#3a86ff)",
            ),

            progress_section(),

            rx.cond(
                State.download_url != "",
                rx.link(
                    rx.button(
                        "Download Source Code",
                        width="100%",
                        size="4",
                        color_scheme="green",
                    ),
                    href=State.download_url,
                    is_external=True,
                ),
            ),

            terminal_window(),

            spacing="6",
            width="100%",
        ),
        width=["100%", "720px"],
        padding="4em",
        border_radius="32px",
        className="glass-card",
        style={"animation": "float 6s ease-in-out infinite"},
    )

def index():
    return rx.center(
        rx.el.style(STYLE_CSS),
        main_card(),
        width="100%",
        min_height="100vh",
        padding="2em",
        className="mesh-bg",
        font_family="'Outfit', sans-serif",
    )

# =========================
# 4️⃣ APP
# =========================

def mount_autodev(app: FastAPI) -> FastAPI:
    app.mount("/autodev", autodevapi)

    build_dir = None
    for root, dirs, files in os.walk("."):
        if "index.html" in files:
            build_dir = root
            break

    if build_dir:
        app.mount("/", StaticFiles(directory=build_dir, html=True), name="static")
    else:
        logger.error("index.html not found.")

    return app

app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="ruby",
        radius="large",
        panel_background="translucent",
    ),
    api_transformer=mount_autodev,
)

app.add_page(index, title="AutoDev AI | Autonomous Architect", on_load=State.reset_state)