from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn
import os
import httpx

from predictor import predict_stock

GITHUB_TOKEN = os.environ.get("PAT_TOKEN", "")
GITHUB_REPO = os.environ.get("REPO_NAME", "")

app = FastAPI(title="Stock Price Predictor")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/predict")
async def predict(ticker: str = Form(...), days: int = Form(7)):
    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker symbol is required.")
    if days not in (7, 14, 30):
        raise HTTPException(status_code=400, detail="Days must be 7, 14, or 30.")
    try:
        result = predict_stock(ticker, days)
        return JSONResponse(content=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.post("/deploy")
async def deploy(prompt: str = Form(...)):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        raise HTTPException(status_code=500, detail="GitHub integration not configured.")
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/deploy.yml/dispatches",
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json"
            },
            json={"ref": "main", "inputs": {"prompt": prompt}}
        )
    if res.status_code != 204:
        raise HTTPException(status_code=500, detail=f"GitHub API error: {res.text}")
    return {"status": "triggered", "prompt": prompt}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)