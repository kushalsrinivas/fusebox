from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .middleware import RateLimitMiddleware
from .routers import actions, admin, billing, clusters, feedback, graph, insights, onboarding, repos, telemetry, verify, webhooks

app = FastAPI(title="Fusebox Gateway", version="0.1.0")

app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# repos first: /v1/webhooks/github must win over /v1/webhooks/{source}
app.include_router(repos.router)
app.include_router(feedback.router)
app.include_router(telemetry.router)
app.include_router(clusters.router)
app.include_router(graph.router)
app.include_router(actions.router)
app.include_router(verify.router)
app.include_router(insights.router)
app.include_router(billing.router)
app.include_router(admin.router)
app.include_router(onboarding.router)
app.include_router(webhooks.router)


@app.get("/healthz")
def healthz():
    return {"ok": True}
