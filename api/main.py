import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import jobs, projects, institutions, matching, settings

app = FastAPI(title="FA Matching API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
for router in [jobs.router, projects.router, institutions.router,
               matching.router, settings.router]:
    app.include_router(router)

@app.get("/api/health")
def health():
    return {"status": "ok"}
