import reflex as rx
import httpx
import json
import os
import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.main import api as autodevapi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autodev_deploy")

# =========================
# CINEMATIC DESIGN SYSTEM
# =========================

STYLE_CSS = """
@keyframes mesh-gradient {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

@keyframes float {
    0% { transform: translateY(0px); }
    50% { transform: translateY(-10px); }
    100% { transform: translateY(0px); }
}

@keyframes glow-pulse {
    0% { box-shadow: 0 0 20px rgba(255,0,150,0.15); }
    50% { box-shadow: 0 0 60px rgba(255,0,200,0.35); }
    100% { box-shadow: 0 0 20px rgba(255,0,150,0.15); }
}

body {
    background: radial-gradient(circle at 20% 20%, rgba(255,0,150,0.08), transparent 40%),
                radial-gradient(circle at 80% 80%, rgba(0,100,255,0.08), transparent 40%),
                #070b14;
}

.mesh-bg {
    background: linear-gradient(-45deg, #0f0c29, #1e1b4b, #1e3a8a, #3b0764);
    background-size: 400% 400%;
    animation: mesh-gradient 25s ease infinite;
}

.glass-card {
    backdrop-filter: blur(45px) saturate(220%);
    -webkit-backdrop-filter: blur(45px) saturate(220%);
    background: linear-gradient(145deg, rgba(15,15,25,0.9), rgba(10,10,20,0.95));
    border: 1px solid rgba(255,255,255,0.06);
    position: relative;
    overflow: hidden;
    animation: float 8s ease-in-out infinite;
}

.glass-card::before {
    content: "";
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at top left, rgba(255,0,150,0.15), transparent 40%);
    pointer-events: none;
}

.glow-button {
    animation: glow-pulse 4s infinite ease-in-out;
}

.glow-button:hover {
    transform: translateY(-4px) scale(1.02);
    transition: all 0.3s ease;
}
"""

# =========================
# STATE (UNCHANGED LOGIC)
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
                                self.logs.append("✨ Build Sequence Complete!")
                                yield
                        except:
                            continue
        except Exception as e:
            self.logs.append(f"❌ Critical Failure: {str(e)}")

        self.is_building = False

# =========================
# UI
# =========================

def index():
    return rx.center(
        rx.el.style(STYLE_CSS),
        rx.box(
            rx.vstack(
                rx.heading(
                    "AutoDev AI",
                    size="9",
                    weight="bold",
                    background_image="linear-gradient(90deg,#ff006e,#8338ec,#3a86ff)",
                    background_clip="text",
                    color="transparent",
                    letter_spacing="-1px",
                ),
                rx.text(
                    "Autonomous Backend System Architect",
                    color="#94a3b8",
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
                    min_height="150px",
                    radius="large",
                ),

                rx.button(
                    "Launch System Build",
                    on_click=State.start_build,
                    loading=State.is_building,
                    width="100%",
                    size="4",
                    className="glow-button",
                    background="linear-gradient(90deg,#ff006e,#8338ec,#3a86ff)",
                ),

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

                rx.cond(
                    State.logs,
                    rx.box(
                        rx.foreach(
                            State.logs,
                            lambda log: rx.text(
                                log,
                                font_family="'JetBrains Mono', monospace",
                                font_size="0.85em",
                                color="#c9d1d9",
                            ),
                        ),
                        margin_top="2em",
                        padding="1.5em",
                        border_radius="16px",
                        bg="rgba(10,15,25,0.8)",
                        border="1px solid rgba(255,255,255,0.05)",
                        width="100%",
                    ),
                ),

                spacing="6",
                width="100%",
            ),
            width=["100%", "760px"],
            padding="5em",
            border_radius="36px",
            className="glass-card",
        ),
        min_height="100vh",
        padding="2em",
        className="mesh-bg",
        font_family="'Outfit', sans-serif",
    )

# =========================
# APP
# =========================

def mount_autodev(app: FastAPI) -> FastAPI:
    # 1. Mount the backend API
    app.mount("/autodev", autodevapi)

    # 2. Serve static files from the "public" directory
    # Note: The "public" directory is created during the build process
    if os.path.exists("public"):
        app.mount("/", StaticFiles(directory="public", html=True), name="static")
    
    # 3. Catch-all route for Client-Side Routing (Single Page App)
    @app.get("/{rest_of_path:path}")
    async def caught_all(request: Request, rest_of_path: str):
        # If it's not an API call and file doesn't exist, serve index.html
        if not rest_of_path.startswith("autodev") and os.path.exists("public/index.html"):
            return FileResponse("public/index.html")
        return {"detail": "Not Found"}

    return app

app = rx.App(
    theme=rx.theme(appearance="dark", accent_color="ruby", radius="large"),
    api_transformer=mount_autodev,
)

app.add_page(index, title="AutoDev AI | Autonomous Architect", on_load=State.reset_state)