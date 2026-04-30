from fastapi import FastAPI

app = FastAPI(title="My Life Movie API")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
