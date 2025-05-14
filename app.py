import os
import sys
import json
import toml
import httpx
import logging
import sqlite3
import hashlib
from typing import List
from yaml import dump, safe_load, YAMLError
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse, FileResponse
from fastapi import HTTPException, Query

config = toml.load("config.toml")
api_core_folder = config["api"]["core_folder"]
api_core_fetching_url = config["api"]["core_fetching_url"]
api_ext_folder = config["api"]["ext_folder"]
sqlite_file = config["cache"]["sqlite_file"]

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
logger.info(f"configs: {json.dumps(config, indent=2)}")

### Cache related functions ###
# Initialize SQLite database
def init_cache_db():
    conn = sqlite3.connect(sqlite_file)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_str TEXT NOT NULL,
            core_file TEXT NOT NULL,
            exts_md5 TEXT NOT NULL,
            output_file TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# Compute MD5 hash of extensions
def compute_md5(ext_files: List[str]) -> str:
    if len(ext_files) == 0:
        raise ValueError("No extension files provided.")
    if not all(os.path.isfile(file) for file in ext_files):
        raise FileNotFoundError("One or more extension files do not exist.")

    md5 = hashlib.md5()
    for ext_file in ext_files:  # Sort to ensure consistent order
        with open(os.path.join(api_ext_folder, ext_file), "rb") as f:
            md5.update(f.read())
    return md5.hexdigest()

# Check cache
def get_cached_file(version_str, core_file, exts_md5):
    conn = sqlite3.connect(sqlite_file)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT output_file FROM cache
        WHERE version_str = ? AND core_file = ? AND exts_md5 = ?
    """, (version_str, core_file, exts_md5))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Add to cache
def add_to_cache(version_str, core_file, exts_md5, output_file):
    conn = sqlite3.connect(sqlite_file)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cache (version_str, core_file, exts_md5, output_file)
        VALUES (?, ?, ?, ?)
    """, (version_str, core_file, exts_md5, output_file))
    conn.commit()
    conn.close()

### End of cache related functions ###

# Getting connection to SQLite database
conn = sqlite3.connect(sqlite_file)

app = FastAPI()

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create a router with a prefix
apir = APIRouter(prefix="/api/ver")


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


def load_or_fetch_core_yaml(version_str: str, core_file: str):
    # Check if the core file exists locally
    local_core_path = os.path.join(api_core_folder, version_str, core_file)
    try:
        with open(local_core_path, 'r') as file:
            logger.info(f"Loading core file from local path: {local_core_path}")
            return safe_load(file)
    except FileNotFoundError:
        # Fetch the core YAML from the URL
        url = api_core_fetching_url.format(version=version_str, filename=core_file)
        logger.info(f"Core file {local_core_path} not found. Fetching from {url}.")
        response = httpx.get(url)
        response.raise_for_status()
        logger.info(f"Fetched core file from {url}.")
        # Save the fetched file locally
        os.makedirs(os.path.dirname(local_core_path), exist_ok=True)
        with open(local_core_path, 'w') as file:
            file.write(response.text)
            logger.info(f"Saved core file to local path: {local_core_path}")
        return safe_load(response.text)


@apir.get("/{version_str}/{core_file}")
def merge_endpoint(version_str: str, core_file: str, ext: List[str] = Query(default=[])):
    logger.info(f"Received request to merge YAML files for version: {version_str}, core_file: {core_file}, extensions: {ext}")
    # append the api_ext_folder to each extension file name
    ext = [os.path.join(api_ext_folder, file) for file in ext]

    if not version_str or not core_file:
        raise FileNotFoundError("Version string or core file name is missing.")
    if len(ext) == 0 or not all(os.path.isfile(file) for file in ext):
        raise FileNotFoundError("One or more extension files do not exist.")

    # Fetch and load the core YAML
    core_yaml = load_or_fetch_core_yaml(version_str, core_file)
    logger.debug(f"Loaded core YAML: {core_yaml}")

    if not core_yaml:
        raise FileNotFoundError("The given version or Core YAML cannot be found.")

    # Fetch and load each extension YAML
    for ext_file in ext:
        logger.info(f"Merging extension file from local path: {ext_file}")
        try:
            with open(ext_file, 'r') as file:
                ext_yaml = safe_load(file)
        except YAMLError as e:
            raise YAMLError(f"Error parsing ext YAML file: {ext_file}.")
        except:
            raise Exception(f"Error loading YAML file: {ext_file}.")

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
    output_filename = f"merged_output_{core_file}_{version_str}.yaml"
    with open(output_filename, "w") as temp_file:
        temp_file.write(dump(core_yaml, sort_keys=False))
    return FileResponse(output_filename, media_type="application/x-yaml", filename=output_filename)



app.include_router(apir)
