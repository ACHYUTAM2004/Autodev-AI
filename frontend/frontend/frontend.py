import reflex as rx
import httpx
import json
import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles # <--- New Import

# Import your backend API
from app.main import api as autodevapi

# Setup Logging so we can SEE what is happening on Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autodev_deploy")

# --- 1. STATE (The Logic) ---
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

    # --- FIX DEPRECATION WARNINGS (Explicit Setters) ---
    def set_project_name(self, value: str):
        self.project_name = value

    def set_description(self, value: str):
        self.description = value

    def set_tech_stack_input(self, value: str):
        self.tech_stack_input = value
    # ---------------------------------------------------

    async def start_build(self):
        """Call the AutoDev API with Streaming."""
        if not self.project_name or not self.description:
            return

        self.is_building = True
        self.logs = [f"🚀 Starting build for '{self.project_name}'..."]
        self.download_url = "" # Reset download link
        yield 

        payload = {
            "project_name": self.project_name,
            "description": self.description,
            "constraints": {
                "tech_preferences": self.tech_stack_input
            }
        }

        # --- THE FIX: Smart URL Detection ---
        # 1. Try to get the real URL from the environment (Render sets RENDER_EXTERNAL_URL)
        domain = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
        
        # 2. Add logging so we can see what URL it is trying to hit
        print(f"🔗 Connecting to Backend at: {domain}")
        self.logs.append(f"🔗 Connecting to: {domain}...")
        yield

        try:
            async with httpx.AsyncClient(base_url=domain, timeout=None) as client:
                async with client.stream(
                    "POST",
                    "/autodev/build", 
                    json=payload
                ) as response:
                    
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
                                self.logs.append("✅ Build Complete!")
                                yield
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            # Print the FULL error to the terminal window so we can debug
            self.logs.append(f"❌ Connection Failed: {str(e)}")
            print(f"❌ CRITICAL ERROR: {e}")
        
        self.is_building = False

# --- 2. UI COMPONENTS (Unchanged) ---
def terminal_window():
    return rx.cond(
        State.logs,
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.text("Build Logs", font_weight="bold", color="white"),
                    rx.spacer(),
                    rx.badge(
                        rx.cond(State.is_building, "Building...", "Idle"),
                        color_scheme=rx.cond(State.is_building, "yellow", "gray"),
                        variant="soft"
                    ),
                    width="100%",
                ),
                rx.scroll_area(
                    rx.vstack(
                        rx.foreach(
                            State.logs,
                            lambda log: rx.text(
                                log,
                                font_family="Fira Code, monospace",
                                font_size="0.85em",
                                color="#9AE6B4",
                            ),
                        ),
                        align_items="start",
                        spacing="2",
                        padding="2",
                    ),
                    height="240px",
                    type="always",
                ),
                spacing="3",
            ),
            bg="#111",
            border_radius="xl",
            border="1px solid rgba(255,255,255,0.08)",
            padding="1.5em",
            width="100%",
            margin_top="2em",
        ),
    )


def main_card():
    return rx.box(
        rx.vstack(
            # Header
            rx.vstack(
                rx.heading("AutoDev AI", size="9", weight="bold"),
                rx.text(
                    "Your Autonomous Backend Engineer",
                    size="3",
                    color="gray"
                ),
                spacing="1",
                align_items="center"
            ),

            rx.divider(),

            # Form Section
            rx.vstack(
                rx.text("Project Configuration", font_weight="bold", size="4"),

                rx.vstack(
                    rx.text("Project Name", size="2", color="gray"),
                    rx.input(
                        placeholder="e.g. super-saas-platform",
                        value=State.project_name,
                        on_change=State.set_project_name,
                        width="100%",
                        radius="large",
                        size="3"
                    ),
                    spacing="1",
                    width="100%",
                ),

                rx.vstack(
                    rx.text("Tech Stack Preferences (Optional)", size="2", color="gray"),
                    rx.input(
                        placeholder="e.g. Python, FastAPI, PostgreSQL",
                        value=State.tech_stack_input,
                        on_change=State.set_tech_stack_input,
                        width="100%",
                        radius="large",
                        size="3"
                    ),
                    spacing="1",
                    width="100%",
                ),

                rx.vstack(
                    rx.text("What should I build?", size="2", color="gray"),
                    rx.text_area(
                        placeholder="Describe your features, APIs, authentication, database models...",
                        value=State.description,
                        on_change=State.set_description,
                        min_height="160px",
                        width="100%",
                        radius="large",
                        size="3"
                    ),
                    spacing="1",
                    width="100%",
                ),

                spacing="4",
                width="100%",
            ),

            # CTA Button
            rx.button(
                rx.hstack(
                    rx.icon("sparkles"),
                    rx.text("Generate Backend"),
                ),
                on_click=State.start_build,
                loading=State.is_building,
                size="4",
                width="100%",
                radius="large",
                variant="solid",
                color_scheme="ruby",
                margin_top="1em",
                box_shadow="0 4px 20px rgba(255,0,100,0.3)",
                cursor="pointer"
            ),

            # Download Section
            rx.cond(
                State.download_url != "",
                rx.box(
                    rx.link(
                        rx.button(
                            rx.hstack(
                                rx.icon("download"),
                                rx.text("Download Source Code"),
                            ),
                            size="4",
                            width="100%",
                            variant="surface",
                            color_scheme="green",
                            radius="large",
                            cursor="pointer",
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
        width=["100%", "720px"],
        padding="3em",
        border_radius="2xl",
        background="rgba(20, 20, 20, 0.85)",
        backdrop_filter="blur(20px)",
        border="1px solid rgba(255,255,255,0.08)",
        box_shadow="0 10px 40px rgba(0,0,0,0.5)",
    )


def index():
    return rx.center(
        main_card(),
        width="100%",
        min_height="100vh",
        padding="2em",
        background="""
        radial-gradient(circle at 20% 20%, #3b0764 0%, transparent 40%),
        radial-gradient(circle at 80% 80%, #1e3a8a 0%, transparent 40%),
        #000000
        """
    )


# --- 3. APP DEFINITION (Recursive Search) ---
def mount_autodev(app: FastAPI) -> FastAPI:
    app.mount("/autodev", autodevapi)

    # 1. SEARCH for the Build Directory
    build_dir = None
    search_start_dirs = ["public", ".web", "frontend_build"]
    
    logger.warning(f"🔍 STARTING SEARCH FOR INDEX.HTML. CWD: {os.getcwd()}")

    # Helper to walk through folders
    for start_dir in search_start_dirs:
        if not os.path.exists(start_dir):
            logger.warning(f"⚠️  Folder not found: {start_dir}")
            continue
            
        # Walk through the directory tree
        for root, dirs, files in os.walk(start_dir):
            if "index.html" in files:
                build_dir = root
                logger.warning(f"✅ FOUND index.html in: {build_dir}")
                break
        if build_dir:
            break

    # 2. MOUNT if found
    if build_dir:
        logger.warning(f"🚀 MOUNTING STATIC FILES FROM: {build_dir}")
        app.mount("/", StaticFiles(directory=build_dir, html=True), name="static")
    else:
        logger.error("❌ CRITICAL: Could not find 'index.html' anywhere. Site will be blank.")

    return app

app = rx.App(
    theme=rx.theme(appearance="dark", accent_color="ruby", radius="large"),
    api_transformer=mount_autodev
)
app.add_page(index)