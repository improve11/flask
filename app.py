from flask import Flask, request, send_file, render_template, url_for
import aiohttp
import asyncio
import zipfile
from io import BytesIO
from cachetools import cached, TTLCache
import requests

app = Flask(__name__)

cache = TTLCache(maxsize=100, ttl=300)  # Кэш с TTL 5 минут

YANDEX_DISK_API_URL = "https://cloud-api.yandex.net/v1/disk/public/resources"

async def fetch_file(file_url: str, session: aiohttp.ClientSession) -> bytes:
    async with session.get(file_url) as response:
        response.raise_for_status()
        return await response.read()

@cached(cache)
def get_files_list(public_key: str) -> list:
    """Получает список файлов по публичной ссылке."""
    params = {"public_key": public_key}
    response = requests.get(YANDEX_DISK_API_URL, params=params)
    response.raise_for_status()
    items = response.json().get("_embedded", {}).get("items", [])
    return items

@app.route('/download_multiple', methods=['POST'])
def download_multiple():
    file_urls = request.form.getlist('file_urls')
    file_names = request.form.getlist('file_names')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def download_files():
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_file(url, session) for url in file_urls]
            return await asyncio.gather(*tasks)

    files_content = loop.run_until_complete(download_files())

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zipf:
        for content, name in zip(files_content, file_names):
            zipf.writestr(name, content)

    zip_buffer.seek(0)

    return send_file(zip_buffer, download_name='files.zip', as_attachment=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    files = []
    public_key = ""

    if request.method == 'POST':
        public_key = request.form.get('public_key')
        files = get_files_list(public_key)

    return render_template('index.html', files=files, public_key=public_key)

if __name__ == '__main__':
    app.run(debug=True)
