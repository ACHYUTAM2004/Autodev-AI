from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ProjectConstraints(BaseModel):
    backend: Optional[str] = Field(None, example="python")
    database: Optional[str] = Field(None, example="sqlite")
    auth: Optional[str] = Field(None, example="jwt")

class BuildRequest(BaseModel):
    project_name: str = Field(..., example="todo-api")
    description: str = Field(..., example="Build a FastAPI based todo app with JWT authentication")
    constraints: Optional[ProjectConstraints] = Field(default_factory=ProjectConstraints)

class BuildResponse(BaseModel):
    project_name: str
    plan: list[str]
    tech_stack: Dict[str, Any]
    files_generated: list[str]
    download_path: str