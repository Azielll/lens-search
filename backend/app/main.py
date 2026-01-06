from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import health, search

app = FastAPI(
    title="LensSearch API",
    description="CLIP-based image search API",
    version="0.1.0",
)

# CORS middleware - allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(search.router, prefix="/api/v1", tags=["search"])


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    # TODO: Load CLIP model, load embeddings index
    # This will be implemented when services are created
    pass


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    # TODO: Cleanup resources if needed
    pass
