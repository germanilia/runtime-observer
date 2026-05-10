import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python-sdk"))

from fastapi import FastAPI
from runtime_observer import init_runtime_observer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("example")

app = FastAPI()
observer = init_runtime_observer.from_env(service_name="runtime-observer-fastapi-example")
observer.instrument_fastapi(app)


@app.get("/hello")
async def hello():
    logger.info("hello route called for token=secret-token-value")
    return {"hello": "world"}


@app.get("/boom")
async def boom():
    logger.warning("about to raise")
    raise RuntimeError("sample failure with password=secret")
