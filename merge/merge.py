import sys
import json
import argparse
from yaml import dump, safe_load, YAMLError

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


def merge(org, src, ident):
    if isinstance(org, dict):
        if isinstance(src, dict):
            for key in src.keys():
                print(ident + "MERGE dict[" + key + "]", file=sys.stderr)
                if key.startswith('+'):
                    # add item
                    k = key[1:]
                    org.update({k: src[key]})
                elif key.startswith('~'):
                    # merge item (depends on type)
                    k = key[1:]
                    if isinstance(org[k], list):
                        org[k].append(src[key])
                    else:
                        org[k] = src[key]
                elif key.startswith('-'):
                    # remove item 
                    k = key[1:]
                    org.pop(k)
                else:
                    merge(org[key], src[key], ident + '  ')
                print(ident + "DONE MERGE dict[" + key + "]", file=sys.stderr)
        else:
            print(ident + "!no MERGE dict", file=sys.stderr)
    elif isinstance(org, list):
        if isinstance(src, list):
            print(ident + "MERGE list", file=sys.stderr)
            for i, item in enumerate(org):
                if i < len(src):
                    print(ident + "MERGE list[" + str(i) + "]", file=sys.stderr)
                    merge(org[i], src[i], ident + '  ')
                    print(ident + "DONE MERGE list[" + str(i) + "]", file=sys.stderr)
        else:
            print(ident + "!no MERGE list", file=sys.stderr)


def merge_ext_to_core(core, ext):
    # check tags
    for key in ext['skg-if-api'].keys():
        if key.startswith("+tag-"):
            print("ADD tag[" + key + "]", file=sys.stderr)
            core['tags'].append(ext['skg-if-api'][key])
    # check paths
    for key in ext['skg-if-api'].keys():
        if key.startswith("+path-"):
            print("ADD path[" + key + "]", file=sys.stderr)
            core['paths'].update(ext['skg-if-api'][key])
    # check schemas
    for key in ext['skg-if-api'].keys():
        if key.startswith("+schema-"):
            print("ADD schema[" + key + "]", file=sys.stderr)
            core['components']['schemas'].update(ext['skg-if-api'][key])
        if key.startswith("~schema-"):
            print("MERGE schema[" + key + "]", file=sys.stderr)
            merge(core['components']['schemas'], ext['skg-if-api'][key], '')

    return core


def load_and_merge(core_file, ext_files):
    core = None
    with open(core_file) as stream:
        try:
            core = safe_load(stream)
        except YAMLError as exc:
            print(exc)

    for ext_file in ext_files:
        ext = None
        with open(ext_file) as stream:
            try:
                ext = safe_load(stream)
            except YAMLError as exc:
                print(exc)

        print(f"Processing extension: {ext_file}", file=sys.stderr)
        core = merge_ext_to_core(core, ext)

    # Debug output
    print("OUTPUT", file=sys.stderr)
    print("vvvvvv", file=sys.stderr)
    print(json.dumps(core, sort_keys=False, indent=2), file=sys.stderr)
    print("^^^^^^", file=sys.stderr)
    print("OUTPUT", file=sys.stderr)

    # The resulting YAML
    print(dump(core, sort_keys=False))


def main():
    parser = argparse.ArgumentParser(description="Merge YAML core and extension files.")
    parser.add_argument("core", help="Path to the core YAML file")
    parser.add_argument("extensions", nargs="+", help="Paths to the extension YAML files")
    args = parser.parse_args()

    load_and_merge(args.core, args.extensions)


if __name__ == "__main__":
    main()
