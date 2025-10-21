from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from nicegui import ui
from app.db import insert_receipt
import httpx

# 1. Create FastAPI app (used by uvicorn)
app = FastAPI(title='Smart Expense Tracker')

# 2. Attach NiceGUI to the FastAPI app
ui.run_with(app)

MAX_BYTES = 20 * 1024 * 1024  # 20 MB

# 3. FastAPI upload endpoint (for API or Swagger)
@app.post('/api/upload')
async def api_upload(file: UploadFile = File(...), user_id: int = Form(...)):
    """Receives uploaded file and stores it in the database."""
    content = await file.read()
    if not content:
        raise HTTPException(400, 'Empty file')
    if len(content) > MAX_BYTES:
        raise HTTPException(413, 'File too large (>20MB)')
    try:
        result = insert_receipt(user_id, content)
        return {
            'ok': True,
            **result,
            'filename': file.filename,
            'size_bytes': len(content),
        }
    except Exception as e:
        raise HTTPException(400, str(e))


# 4. NiceGUI Frontend
@ui.page('/')
def index_page():
    ui.markdown('# Upload Receipt')
    user_input = ui.number(label='User ID', value=1, min=1).props(
        'dense outlined style="max-width:200px"'
    )
    ui.markdown('Select a file **or** drag & drop. On mobile you can open the camera directly.')

    upload = ui.upload(
        label='Select or drop a file',
        auto_upload=False,
        multiple=False,
    ).props('accept=".heic,.heif,.jpg,.jpeg,.png,.webp,image/*"').classes('max-w-xl')

    camera = ui.upload(
        label='Take a photo (mobile)',
        auto_upload=False,
        multiple=False,
    ).props('accept="image/*" capture=environment').classes('max-w-xl')

    output = ui.markdown('–').classes('mt-4')

    async def send_file(file_dict: dict):
        if not file_dict:
            output.set_content('Please select a file first.')
            return
        try:
            user_id = int(user_input.value or 0)
            if user_id < 1:
                output.set_content('Invalid User ID.')
                return
            data = {'user_id': str(user_id)}
            files = {'file': (file_dict['name'], file_dict['content'])}
            async with httpx.AsyncClient() as client:
                r = await client.post('http://127.0.0.1:8000/api/upload', data=data, files=files)
            output.set_content(r.text)
        except Exception as e:
            output.set_content(f'Error: {e!s}')

    def upload_file_action():
        if upload.files:
            ui.run_async(send_file(upload.files[0]))
        else:
            output.set_content('Please select a file.')

    def camera_file_action():
        if camera.files:
            ui.run_async(send_file(camera.files[0]))
        else:
            output.set_content('Please take a photo first.')

    ui.button('Upload', on_click=upload_file_action)
    ui.button('Save Photo', on_click=camera_file_action)


# 5. Do not call ui.run() here
# FastAPI will serve everything when running with:
# uvicorn app.main:app --reload
