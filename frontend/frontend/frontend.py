import reflex as rx
import httpx
import json
import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Import your backend API
from app.main import api as autodevapi

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autodev_deploy")

# --- 1. STYLES & ANIMATIONS ---
# Custom CSS for premium effects
STYLE_CSS = """
@keyframes mesh-gradient {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

@keyframes pulse-glow {
    0% { box-shadow: 0 0 5px rgba(255, 0, 100, 0.2); }
    50% { box-shadow: 0 0 20px rgba(255, 0, 100, 0.4); }
    100% { box-shadow: 0 0 5px rgba(255, 0, 100, 0.2); }
}

@keyframes scanline {
    0% { transform: translateY(-100%); }
    100% { transform: translateY(100%); }
}

.glass-card {
    backdrop-filter: blur(25px) saturate(180%);
    -webkit-backdrop-filter: blur(25px) saturate(180%);
    background-color: rgba(17, 17, 17, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.125);
}

.mesh-bg {
    background: linear-gradient(-45deg, #0f0c29, #302b63, #24243e, #1e3a8a, #3b0764);
    background-size: 400% 400%;
    animation: mesh-gradient 15s ease infinite;
}

.terminal-scroll::-webkit-scrollbar {
    width: 6px;
}
.terminal-scroll::-webkit-scrollbar-track {
    background: rgba(0,0,0,0.1);
}
.terminal-scroll::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.1);
    border-radius: 10px;
}

.button-glow:hover {
    box-shadow: 0 0 20px rgba(255, 0, 100, 0.6);
    transform: translateY(-2px);
    transition: all 0.3s ease;
}
"""

# --- 2. STATE ---
class State(rx.State):
    """The app state."""
    project_name: str = ""
    description: str = ""
    tech_stack_input: str = ""
    
    # UI State
    is_building: bool = False
    build_result: dict = {}
    logs: list[str] = []
    download_url: str = ""

    def set_project_name(self, value: str):
        self.project_name = value

    def set_description(self, value: str):
        self.description = value

    def set_tech_stack_input(self, value: str):
        self.tech_stack_input = value

    async def start_build(self):
        """Call the AutoDev API with Streaming."""
        if not self.project_name or not self.description:
            return

        self.is_building = True
        self.logs = [f"🚀 Initializing build sequence for '{self.project_name}'..."]
        self.download_url = ""
        yield 

        payload = {
            "project_name": self.project_name,
            "description": self.description,
            "constraints": {
                "tech_preferences": self.tech_stack_input
            }
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
                        if not line: continue
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

# --- 3. UI COMPONENTS ---

def terminal_window():
    return rx.cond(
        State.logs,
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.circle(size="3", bg="#ff5f56"),
                    rx.circle(size="3", bg="#ffbd2e"),
                    rx.circle(size="3", bg="#27c93f"),
                    rx.text("Build Console", font_weight="600", color="gray", size="2", margin_left="1em"),
                    rx.spacer(),
                    rx.badge(
                        rx.cond(State.is_building, "RUNNING", "STABLE"),
                        color_scheme=rx.cond(State.is_building, "yellow", "green"),
                        variant="soft",
                        padding_x="1em",
                        radius="full",
                    ),
                    width="100%",
                    padding_bottom="1em",
                ),
                rx.scroll_area(
                    rx.vstack(
                        rx.foreach(
                            State.logs,
                            lambda log: rx.text(
                                log,
                                font_family="'JetBrains Mono', monospace",
                                font_size="0.8em",
                                color="#adbac7",
                                line_height="1.5",
                            ),
                        ),
                        align_items="start",
                        spacing="1",
                    ),
                    height="200px",
                    className="terminal-scroll",
                ),
                spacing="0",
            ),
            bg="rgba(13, 17, 23, 0.95)",
            border_radius="12px",
            border="1px solid rgba(255,255,255,0.05)",
            padding="1.2em",
            width="100%",
            margin_top="2em",
            box_shadow="0 8px 32px rgba(0,0,0,0.4)",
        ),
    )

def input_field(label, placeholder, value, on_change, icon, **kwargs):
    return rx.vstack(
        rx.hstack(
            rx.icon(icon, size=14, color="gray"),
            rx.text(label, size="2", font_weight="500", color="gray"),
            spacing="2",
            align_items="center",
        ),
        rx.input(
            placeholder=placeholder,
            value=value,
            on_change=on_change,
            width="100%",
            radius="large",
            size="3",
            variant="surface",
            background="rgba(255,255,255,0.03)",
            border="1px solid rgba(255,255,255,0.1)",
            _focus={"border": "1px solid rgba(255,0,100,0.5)", "box_shadow": "0 0 10px rgba(255,0,100,0.1)"},
            **kwargs,
        ),
        spacing="2",
        width="100%",
    )

def main_card():
    return rx.box(
        rx.vstack(
            # Header
            rx.vstack(
                rx.heading("AutoDev AI", size="9", weight="bold", background_image="linear-gradient(90deg, #ff006e, #8338ec)", background_clip="text", color="transparent"),
                rx.text(
                    "Your Autonomous Backend Architect",
                    size="4",
                    color="#adbac7",
                    weight="medium",
                ),
                spacing="2",
                align_items="center"
            ),

            rx.divider(background="rgba(255,255,255,0.05)", margin_y="1em"),

            # Form Section
            rx.vstack(
                input_field("Project Name", "e.g. cloud-nexus-api", State.project_name, State.set_project_name, "folder-plus"),
                input_field("Tech Preferences", "e.g. Go, Gin, Redis", State.tech_stack_input, State.set_tech_stack_input, "cpu"),
                
                rx.vstack(
                    rx.hstack(
                        rx.icon("file-text", size=14, color="gray"),
                        rx.text("System Requirements", size="2", font_weight="500", color="gray"),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.text_area(
                        placeholder="What should I build? E.g. A multi-tenant SaaS with Stripe integration...",
                        value=State.description,
                        on_change=State.set_description,
                        min_height="140px",
                        width="100%",
                        radius="large",
                        size="3",
                        variant="surface",
                        background="rgba(255,255,255,0.03)",
                        border="1px solid rgba(255,255,255,0.1)",
                        _focus={"border": "1px solid rgba(255,0,100,0.5)"},
                    ),
                    spacing="2",
                    width="100%",
                ),

                spacing="5",
                width="100%",
            ),

            # CTA Button
            rx.button(
                rx.hstack(
                    rx.icon("sparkles", size=20),
                    rx.text("Synthesize System", weight="bold"),
                    spacing="3",
                ),
                on_click=State.start_build,
                loading=State.is_building,
                size="4",
                width="100%",
                radius="xl",
                variant="solid",
                color_scheme="ruby",
                margin_top="1.5em",
                className="button-glow",
                cursor="pointer",
                background="linear-gradient(90deg, #ff006e, #8338ec)",
                transition="all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
            ),

            # Download Section
            rx.cond(
                State.download_url != "",
                rx.box(
                    rx.link(
                        rx.button(
                            rx.hstack(
                                rx.icon("download", size=18),
                                rx.text("Download Source Code", weight="bold"),
                            ),
                            size="4",
                            width="100%",
                            variant="surface",
                            color_scheme="green",
                            radius="xl",
                            cursor="pointer",
                            background="rgba(40, 167, 69, 0.1)",
                            border="1px solid rgba(40, 167, 69, 0.3)",
                        ),
                        href=State.download_url,
                        is_external=True,
                        width="100%",
                    ),
                    margin_top="1em",
                ),
            ),

            # Logs
            terminal_window(),

            spacing="6",
            width="100%",
        ),
        width=["100%", "680px"],
        padding="3.5em",
        border_radius="32px",
        className="glass-card",
        box_shadow="0 25px 50px -12px rgba(0, 0, 0, 0.5)",
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

# --- 4. APP DEFINITION ---
def mount_autodev(app: FastAPI) -> FastAPI:
    app.mount("/autodev", autodevapi)

    build_dir = None
    search_start_dirs = ["public", ".web", "frontend_build"]
    
    logger.info(f"🔍 Searching for build artifacts in {os.getcwd()}")

    for start_dir in search_start_dirs:
        if not os.path.exists(start_dir): continue
        for root, dirs, files in os.walk(start_dir):
            if "index.html" in files:
                build_dir = root
                break
        if build_dir: break

    if build_dir:
        logger.info(f"🚀 Mounting static files from: {build_dir}")
        app.mount("/", StaticFiles(directory=build_dir, html=True), name="static")
    else:
        logger.error("❌ Critical: index.html not found.")

    return app

app = rx.App(
    theme=rx.theme(
        appearance="dark", 
        accent_color="ruby", 
        radius="large",
        panel_background="translucent"
    ),
    api_transformer=mount_autodev,
    head_components=[
        rx.el.link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=JetBrains+Mono&display=swap"),
    ],
)
app.add_page(index, title="AutoDev AI | Autonomous Architect")