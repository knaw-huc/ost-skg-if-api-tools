# OpenAPI merge spec

### Installation
```shell
uv add ost-skg-if-api-tools
#or
pip install ost-skg-if-api-tools
```

### Usage
1. as a command line tool:
```shell
source .venv/bin/activate
merge merge/API/core/skg-if-api.yaml merge/API/ext/service.yaml
```
**there can be more than one extension file, e.g. `merge/API/ext/service.yaml merge/API/ext/another.yaml`**
2. as a python module:
```python
from merge.merge import load_and_merge
load_and_merge(
    core_file="merge/API/core/skg-if-api.yaml",
    ext_files=["merge/API/ext/service.yaml", "merge/API/ext/another.yaml"]
)
```
3. as a web service:
TBD



Specify what should be changed in/added to the SKG-IF OpenAPI YAML, which supports the core SKG-IF data model, for an extension. RThis document will use an example __server__ extension.

## Header

Identify the extension. Potentially specify which extension(s) it extends and should already have been merged in the core OpenAPI YAML.

```yaml
extension: service
# depends-on: foo
# depends-on: bar
skg-if-api:
```

## Add tags
Add one or more tags. Each tag key, e.g. `tag-service`, should be unique. The `+` prefix tells the merger to add the tag.

```yaml
  +tag-service:
    name: Service
    description: Lorem ipsum dolor sit amet. 
  #+tag-another:
```

## Add schemas

Add one or more schemas. Each schema key, e.g. `path-service`, should be unique. The `+` prefix tells the merger to add the schema.

```yaml
  +path-service:
    '/services/{local_identifier}':
      get:
        tags:
            - Service
  ...
  +path-services:
    '/services':
      get:
        tags:
            - Service
  ...
```

### Modify a schema

Modify an existing (core) schema. Add the `~` prefix to the key of the schema to modify. Then copy all the steps that are needed to get to where a field has to be added or modified. In the example below its up to `properties`, to which `services` is added indicated by the `+` prefix. To step into the right item of a list the right position can be achieved with empty `-` items. The `~enum` showcases a modification of its value list, i.e. adding the `portal` value.

```yaml
~schema-venue:
    Venue:
      allOf:
        -
        - type: object
          properties:
            type:
              ~enum: portal
            +services:
              type: array
              items:
                $ref: '#/components/schemas/Service'
```