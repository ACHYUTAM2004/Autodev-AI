import reflex as rx
import httpx
import json
from app.main import api as autodevapi
from fastapi import FastAPI

# --- 1. STATE (The Logic) ---
class State(rx.State):
    """The app state."""
    project_name: str = ""
    description: str = ""
    tech_stack_input: str = ""  # New free-text field
    
    # UI State
    is_building: bool = False
    build_result: dict = {}
    logs: list[str] = []

    async def start_build(self):
        """Call the AutoDev API with Streaming."""
        if not self.project_name or not self.description:
            return

        self.is_building = True
        self.logs = [f"🚀 Starting build for '{self.project_name}'..."]
        yield 

        payload = {
            "project_name": self.project_name,
            "description": self.description,
            "constraints": {
                "tech_preferences": self.tech_stack_input
            }
        }

        try:
            async with httpx.AsyncClient() as client:
                # Use .stream() instead of .post()
                async with client.stream(
                    "POST",
                    "/autodev/build",
                    json=payload, 
                    timeout=None # No timeout for streams
                ) as response:
                    
                    # Read line by line as they arrive
                    async for line in response.aiter_lines():
                        if not line: continue
                        
                        try:
                            # Parse the JSON line
                            data = json.loads(line)
                            
                            if data["type"] == "log":
                                # Update UI with new log immediately
                                self.logs.append(data["content"])
                                yield # Trigger UI update
                                
                            elif data["type"] == "result":
                                # Handle success
                                self.build_result = data["data"]
                                self.logs.append("✅ Build Complete!")
                                self.logs.append(f"📂 Saved to: {self.build_result.get('download_path')}")
                                yield
                                
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            self.logs.append(f"❌ Connection Failed: {str(e)}")
        
        self.is_building = False


# --- 2. UI COMPONENTS (The Look) ---

def terminal_window():
    """A cool retro-style terminal for logs."""
    return rx.box(
        rx.hstack(
            # --- FIX: Use rx.box with border_radius="full" instead of rx.circle ---
            rx.box(width="12px", height="12px", bg="#FF5F56", border_radius="full"),
            rx.box(width="12px", height="12px", bg="#FFBD2E", border_radius="full"),
            rx.box(width="12px", height="12px", bg="#27C93F", border_radius="full"),
            # ----------------------------------------------------------------------
            spacing="2",
            padding="2",
            bg="rgba(255, 255, 255, 0.1)",
            border_bottom="1px solid rgba(255,255,255,0.1)"
        ),
        rx.scroll_area(
            rx.vstack(
                rx.foreach(
                    State.logs,
                    lambda log: rx.text(
                        "> " + log, 
                        font_family="Fira Code, monospace", 
                        font_size="0.9em",
                        color="lightgreen"
                    )
                ),
                align_items="start",
                spacing="1",
                padding="4",
            ),
            height="200px",
            type="always",
        ),
        bg="#0f0f0f",
        border_radius="lg",
        width="100%",
        border="1px solid #333",
        margin_top="2em",
        display=rx.cond(State.logs, "block", "none") 
    )

def main_card():
    return rx.card(
        rx.vstack(
            rx.heading("AutoDev AI", size="8", weight="bold", color_scheme="ruby"),
            rx.text(
                "Autonomous Software Engineer", 
                size="3", 
                color="gray", 
                margin_bottom="1em"
            ),
            
            # --- INPUTS ---
            rx.vstack(
                rx.text("Project Name", font_weight="bold", size="2"),
                rx.input(
                    placeholder="e.g. super-saas-platform", 
                    value=State.project_name,
                    on_change=State.set_project_name,
                    width="100%",
                    variant="soft",
                    radius="full"
                ),
                width="100%",
                spacing="2"
            ),

            rx.vstack(
                rx.text("Tech Stack Preferences", font_weight="bold", size="2"),
                rx.input(
                    placeholder="e.g. Python, Django, Postgres (Leave empty for auto-detect)",
                    value=State.tech_stack_input,
                    on_change=State.set_tech_stack_input,
                    width="100%",
                    variant="soft",
                    radius="full"
                ),
                rx.text(
                    "Tip: You can ask for 'Node.js', 'Go', 'React', or anything else.", 
                    size="1", 
                    color="gray"
                ),
                width="100%",
                spacing="2"
            ),
            
            rx.vstack(
                rx.text("What should I build?", font_weight="bold", size="2"),
                rx.text_area(
                    placeholder="Describe your features, database models, and API endpoints...",
                    value=State.description,
                    on_change=State.set_description,
                    min_height="150px",
                    width="100%",
                    variant="soft",
                    radius="large"
                ),
                width="100%",
                spacing="2"
            ),
            
            rx.button(
                rx.hstack(
                    rx.icon("sparkles"),
                    rx.text("Generate Backend"),
                ),
                on_click=State.start_build,
                loading=State.is_building,
                size="4",
                width="100%",
                variant="solid",
                color_scheme="ruby",
                margin_top="1em",
                cursor="pointer"
            ),
            
            terminal_window(),
            
            spacing="5",
            align_items="start",
            padding="2em",
        ),
        width=["100%", "600px"], # Responsive width
        background="rgba(20, 20, 20, 0.8)",
        backdrop_filter="blur(10px)",
        border="1px solid rgba(255, 255, 255, 0.1)",
        box_shadow="0 8px 32px 0 rgba(0, 0, 0, 0.37)",
    )

def index():
    return rx.center(
        main_card(),
        width="100%",
        min_height="100vh",
        background="radial-gradient(circle at 50% 10%, #2a1b3d 0%, #000000 100%)", # Deep purple/black gradient
        padding="2em"
    )

# --- 3. APP DEFINITION ---
# 1. Create a Master FastAPI App (The Wrapper)
# This replaces the old 'app.api.mount' logic
meta_app = FastAPI()
meta_app.mount("/autodev", autodevapi)

# 2. Initialize Reflex with the Master App
app = rx.App(
    theme=rx.theme(
        appearance="dark", 
        accent_color="ruby", 
        radius="large"
    ),
    # This tells Reflex: "Use this existing FastAPI app as the base"
    api_transformer=meta_app  
)

app.add_page(index)
