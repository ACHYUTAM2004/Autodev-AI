import reflex as rx
import os

config = rx.Config(
    app_name="frontend",
    # On Render, this will automatically use the production URL
    api_url=os.getenv("RENDER_EXTERNAL_URL", "http://localhost:3000")
)