from fastapi import FastAPI

app = FastAPI(
    title="AutoDev AI",
    version="0.1.0",
    description="Autonomous Software Engineer Agent"
)


@app.get("/health")
def health_check():
    return {"status": "ok"}
