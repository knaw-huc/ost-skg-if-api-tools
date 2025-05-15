import os
import sys
import json
import toml
import httpx
import logging
import sqlite3
import hashlib
from typing import List, Optional
from yaml import dump, safe_load, YAMLError
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse, FileResponse
from fastapi import HTTPException, Query

config = toml.load("config.toml")
api_core_folder: str = config["api"]["core_folder"]
api_core_fetching_url: str = config["api"]["core_fetching_url"]
api_ext_folder: str = config["api"]["ext_folder"]
sqlite_file: str = config["cache"]["sqlite_file"]
ext_postfix: List[str] = config["api"]["ext"]["ext_postfix"]
output_folder: str = config["api"]["output_folder"]

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
    logger.info("Initializing SQLite database for caching...")
    conn = sqlite3.connect(sqlite_file)
    cursor = conn.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS cache
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       version_str
                       TEXT
                       NOT
                       NULL,
                       core_file
                       TEXT
                       NOT
                       NULL,
                       exts_md5
                       TEXT
                       NOT
                       NULL,
                       output_file
                       TEXT
                       NOT
                       NULL
                   )
                   """)
    conn.commit()
    return conn


# Compute MD5 hash of extensions
def compute_md5(ext_files: List[str]) -> str:
    md5 = hashlib.md5()
    for ext_file in ext_files:  # Sort to ensure consistent order
        with open(ext_file, "rb") as f:
            md5.update(f.read())
    return md5.hexdigest()


# Check cache
def get_cached_file(version_str, core_file, exts_md5):
    conn = sqlite3.connect(sqlite_file)
    cursor = conn.cursor()
    cursor.execute("""
                   SELECT output_file
                   FROM cache
                   WHERE version_str = ?
                     AND core_file = ?
                     AND exts_md5 = ?
                   """, (version_str, core_file, exts_md5))
    result = cursor.fetchone()

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



### End of cache related functions ###

# Getting connection to SQLite database
conn = init_cache_db()

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


def get_files_in_folder(folder: str = api_ext_folder, include_path: bool = False, postfixes: Optional[List[str]] = None) -> List[str]:
    if postfixes is None:
        postfixes = ext_postfix

    files = []
    for file in os.listdir(folder):
        if any(file.endswith(postfix) for postfix in postfixes):
            files.append(os.path.join(folder, file) if include_path else file)
    return files


def clean_ext(ext: List[str], ext_folder_to_clean: str = api_ext_folder) -> List[str]:
    existing_ext_files: List[str] = get_files_in_folder(ext_folder_to_clean, False, ext_postfix)
    logger.info(f"Extension files in folder: {existing_ext_files}")
    # remove postfix if there
    ext = [os.path.splitext(os.path.basename(file))[0] for file in ext]
    # remove duplicates
    if len(ext) != len(set(ext)):
        raise ValueError("Duplicate extensions found.")
    # check if all extensions exist
    for item in ext:
        matching_file = next((f"{item}{postfix}" for postfix in ext_postfix if f"{item}{postfix}" in existing_ext_files), None)
        if not matching_file:
            raise FileNotFoundError(f"Extension '{item}' does not exist.")
        ext[ext.index(item)] = matching_file

    return ext

def validate_core(version_str: str, core_file: str):
    if not version_str or not core_file:
        raise FileNotFoundError("Version string or core file name is missing.")
    # Fetch and load the core YAML
    core_yaml = load_or_fetch_core_yaml(version_str, core_file)
    if not core_yaml:
        raise FileNotFoundError("The given version or Core YAML cannot be found.")
    logger.debug(f"Core YAML OK! Loaded core YAML: {core_yaml}")
    return core_yaml


def validate_ext(ext: List[str]):
    if len(ext) == 0:
        raise FileNotFoundError("No extension files provided.")
    # make sure the requested ext files exist and get the file names
    ext = clean_ext(ext)
    # add full path to ext files
    ext = [os.path.join(api_ext_folder, file) for file in ext]
    logger.info("Extension OK!")
    logger.debug(f"Extension files: {ext}")
    return ext


def save_output(core_yaml, output_filename: str):
    with open(output_filename, "w") as temp_file:
        temp_file.write(dump(core_yaml, sort_keys=False))
    logger.info(f"Saved merged YAML to {output_filename}")


@apir.get("/{version_str}/{core_file}")
def merge_endpoint(version_str: str, core_file: str, ext: List[str] = Query(default=[])):
    logger.info(
        f"Received request to merge YAML files for version: {version_str}, core_file: {core_file}, extensions: {ext}")

    # validate core
    core_yaml = validate_core(version_str, core_file)
    # validate ext
    ext = validate_ext(ext)

    # Check cache for existing merged file
    exts_md5 = compute_md5(ext)
    cached_file = get_cached_file(version_str, core_file, exts_md5)
    if cached_file:
        logger.info(f"Using cached merged file: {cached_file}")
        return FileResponse(cached_file, media_type="application/x-yaml", filename=os.path.basename(cached_file))


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
    output_filename = os.path.join(output_folder, f"merged_output_{core_file}_{version_str}.yaml")
    save_output(core_yaml, output_filename)
    # Add to cache
    add_to_cache(version_str, core_file, exts_md5, output_filename)
    return FileResponse(output_filename, media_type="application/x-yaml", filename=f"merged_output_{core_file}_{version_str}.yaml")


app.include_router(apir)
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
