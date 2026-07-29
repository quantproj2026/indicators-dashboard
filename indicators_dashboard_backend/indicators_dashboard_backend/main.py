from fastapi import FastAPI

app = FastAPI(
    title="Indicators Dashboard",
    description="Backend API for the indicators dashboard",
    version="0.1.0",
)

@app.get("/")
def root():
    return {"message": "Indicators Dashboard API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}