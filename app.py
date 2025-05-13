import sys
import json
import toml
import httpx
import logging
from typing import List
from yaml import dump, safe_load, YAMLError
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse
from fastapi import HTTPException, Query

config = toml.load("pyproject.toml")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("fastapi-logger")

logger.info("Starting SKG-IF specification merge api ...")
app = FastAPI()

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create a router with a prefix
apir = APIRouter(prefix="/api")


def merge(org, src, ident):
    if isinstance(org, dict):
        if isinstance(src, dict):
            for key in src.keys():
                if key.startswith('+'):
                    k = key[1:]
                    org.update({k: src[key]})
                elif key.startswith('~'):
                    k = key[1:]
                    if isinstance(org[k], list):
                        org[k].append(src[key])
                    else:
                        org[k] = src[key]
                elif key.startswith('-'):
                    k = key[1:]
                    org.pop(k)
                else:
                    merge(org[key], src[key], ident + '  ')
        else:
            pass
    elif isinstance(org, list):
        if isinstance(src, list):
            for i, item in enumerate(org):
                if i < len(src):
                    merge(org[i], src[i], ident + '  ')


@apir.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI app!"}


@apir.get("/merge")
def merge_endpoint(core: str, ext: List[str] = Query(...)):
    try:
        # Fetch and load the core YAML
        core_response = httpx.get(core)
        core_response.raise_for_status()
        core_yaml = safe_load(core_response.text)

        # Fetch and load each extension YAML
        for ext_url in ext:
            ext_response = httpx.get(ext_url)
            ext_response.raise_for_status()
            ext_yaml = safe_load(ext_response.text)

            # Merge tags
            for key in ext_yaml.get('skg-if-api', {}).keys():
                if key.startswith("+tag-"):
                    core_yaml['tags'].append(ext_yaml['skg-if-api'][key])

            # Merge paths
            for key in ext_yaml.get('skg-if-api', {}).keys():
                if key.startswith("+path-"):
                    core_yaml['paths'].update(ext_yaml['skg-if-api'][key])

            # Merge schemas
            for key in ext_yaml.get('skg-if-api', {}).keys():
                if key.startswith("+schema-"):
                    core_yaml['components']['schemas'].update(ext_yaml['skg-if-api'][key])
                if key.startswith("~schema-"):
                    merge(core_yaml['components']['schemas'], ext_yaml['skg-if-api'][key], '')

        # Return the resulting YAML
        return dump(core_yaml, sort_keys=False)

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Error fetching YAML: {e}")
    except YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Error parsing YAML: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


app.include_router(apir)
