import httpx
import random
import base64
import asyncio
from fastapi import FastAPI, Request, HTTPException
from starlette.responses import Response

# === KONFIGURASI ===
PROXY_SOURCE_URL = "https://raw.githubusercontent.com/gunturyogatama404/proxy-listhh/refs/heads/main/proxies.txt"
USERNAME = "admin"
PASSWORD = "password"
TIMEOUT = 10

LIVE_PROXIES = []

app = FastAPI()

# === AUTENTIKASI ===
def auth_valid(auth: str):
    try:
        scheme, encoded = auth.split()
        decoded = base64.b64decode(encoded).decode()
        return decoded == f"{USERNAME}:{PASSWORD}"
    except:
        return False

# === PROXY CHECKER ===
async def check_proxy(proxy):
    try:
        async with httpx.AsyncClient(proxies=proxy, timeout=TIMEOUT) as client:
            r = await client.get("https://api.ipify.org")
            return proxy
    except:
        return None

async def fetch_proxies_from_url():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(PROXY_SOURCE_URL)
            return [line.strip() for line in r.text.splitlines() if line.strip()]
    except Exception as e:
        print(f"❌ Gagal mengambil proxies dari URL: {e}")
        return []

async def filter_live_proxies():
    proxies = await fetch_proxies_from_url()
    tasks = [check_proxy(p) for p in proxies]
    results = await asyncio.gather(*tasks)
    return list(filter(None, results))

# === LOAD ON STARTUP ===
@app.on_event("startup")
async def load_proxies():
    global LIVE_PROXIES
    print("🔍 Mengambil & mengecek proxy aktif...")
    LIVE_PROXIES = await filter_live_proxies()
    if not LIVE_PROXIES:
        print("❌ Tidak ada proxy aktif ditemukan!")
    else:
        print(f"✅ {len(LIVE_PROXIES)} proxy aktif tersedia.")

# === ROUTER UTAMA ===
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy(path: str, request: Request):
    global LIVE_PROXIES

    if "authorization" not in request.headers or not auth_valid(request.headers["authorization"]):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not LIVE_PROXIES:
        raise HTTPException(status_code=503, detail="No live proxies available.")

    proxy = random.choice(LIVE_PROXIES)
    try:
        url = str(request.url)
        async with httpx.AsyncClient(proxies=proxy, timeout=TIMEOUT) as client:
            r = await client.request(
                method=request.method,
                url=url,
                headers={k: v for k, v in request.headers.items() if k.lower() != 'host'},
                content=await request.body()
            )
        return Response(status_code=r.status_code, content=r.content, headers=r.headers)
    except Exception as e:
        print(f"⚠️ Proxy gagal: {proxy}")
        if proxy in LIVE_PROXIES:
            LIVE_PROXIES.remove(proxy)
        raise HTTPException(status_code=502, detail=f"Proxy failed: {proxy}")
