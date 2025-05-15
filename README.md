# ost-skg-if-api-tools
OSTrails - SKG IF - API - tools

### How to run
1. Clone the repository
2. `docker build -t skgif:test .`
3. `docker compose up -d`

The stack will be up and running with `fastapi` on port `8000:8000` and `nginx` on port `8080:80`

4. Visit `http://localhost:8000/api/ver` to see the nginx welcome page.
5. Visit `http://localhost:8000/api/ver/1.1.3/skg-if-api.yaml?ext=service` to download the merged yaml file.

### Config
The config file is `config.toml` in the root directory. 
```toml
[api]
core_folder = "merge/API/core"
#core_fetching_url = "https://github.com/skg-if/api/openapi/ver/{version}/{filename}"
core_fetching_url = "http://nginx/{version}/{filename}"
ext_folder = "merge/API/ext"
output_folder = "merge/API/output"

[api.ext]
ext_postfix = [".yaml", ".yml"]

[cache]
sqlite_file = "cache.db"
```

1. `core_folder` is the folder where the core yaml files are cached.
2. When cache missing, the core yaml files will be fetched from `core_fetching_url` and saved in `core_folder`.
3. `{version}` is the version of the core yaml file and `{filename}` is the filename of the core yaml file.
4. `ext_folder` is the folder where the ext yaml files are stored.
5. `output_folder` is the folder where the merged yaml files are saved. It serves as cache for the merged yaml files.
6. `ext_postfix` is the postfix of the ext yaml filee, the yaml file can be `.yaml` or `.yml`.
7. `sqlite_file` is the sqlite db where cache information is stored.

### Testing
For testing purpose, endpoint `clear_cache` is made to remove all the cache entries in the sqlite db.
