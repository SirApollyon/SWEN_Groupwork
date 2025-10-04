from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse

app = FastAPI(title="Smart Expense Tracker", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html><body>
      <h3>Upload test</h3>
      <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="receipt" accept="image/*,application/pdf"/>
        <button type="submit">Upload</button>
      </form>
    </body></html>
    """

@app.post("/upload")
async def upload(receipt: UploadFile = File(...)):
    allowed = {"image/jpeg","image/png","application/pdf"}
    if receipt.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    # noch keine Speicherung/OCR – nur Echo
    return {"filename": receipt.filename, "content_type": receipt.content_type}
