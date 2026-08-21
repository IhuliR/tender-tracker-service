from fastapi import FastAPI

from app.routers.tenders import router as tenders_router

app = FastAPI()
app.include_router(tenders_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok"}
