import sys
import json
from yaml import dump, safe_load, YAMLError
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def merge(org, src, ident):
    if isinstance(org, dict):
        if isinstance(src, dict):
            for key in src.keys():
                print(ident+"MERGE dict["+key+"]",file=sys.stderr)
                if key.startswith('+'):
                    # add item
                    k = key[1:]
                    org.update({k:src[key]})
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
                    merge(org[key],src[key],ident+'  ')
                print(ident+"DONE MERGE dict["+key+"]",file=sys.stderr)
        else:
            print(ident+"!no MERGE dict",file=sys.stderr)
    elif isinstance(org, list):
        if isinstance(src, list):
            print(ident+"MERGE list",file=sys.stderr)
            for i, item in enumerate(org):
                if i < len(src):
                    print(ident+"MERGE list["+str(i)+"]",file=sys.stderr)
                    merge(org[i],src[i], ident+'  ')
                    print(ident+"DONE MERGE list["+str(i)+"]",file=sys.stderr)
        else:
            print(ident+"!no MERGE list",file=sys.stderr)
    

def merge_ext_to_core(core, ext):
    #check tags
    for key in ext['skg-if-api'].keys():
        if key.startswith("+tag-"):
            print("ADD tag["+key+"]",file=sys.stderr)
            core['tags'].append(ext['skg-if-api'][key])
    #check paths
    for key in ext['skg-if-api'].keys():
        if key.startswith("+path-"):
            print("ADD path["+key+"]",file=sys.stderr)
            core['paths'].update(ext['skg-if-api'][key])
    #check schemas
    for key in ext['skg-if-api'].keys():
        if key.startswith("+schema-"):
            print("ADD schema["+key+"]",file=sys.stderr)
            core['components']['schemas'].update(ext['skg-if-api'][key])
        if key.startswith("~schema-"):
            print("MERGE schema["+key+"]",file=sys.stderr)
            merge(core['components']['schemas'],ext['skg-if-api'][key],'')

    return core

def main():
    args = sys.argv[1:]

    core =None
    with open(args[0]) as stream:
        try:
            core = safe_load(stream)
        except YAMLError as exc:
            print(exc)

    ext = None
    with open(args[1]) as stream:
        try:
            ext =safe_load(stream)
        except YAMLError as exc:
            print(exc)

    print("CORE",file=sys.stderr)
    print("vvvv",file=sys.stderr)
    print(json.dumps(core,indent=2),file=sys.stderr)
    print("^^^^",file=sys.stderr)
    print("CORE",file=sys.stderr)

    print("EXTENSION",file=sys.stderr)
    print("vvvvvvvvv",file=sys.stderr)
    print(json.dumps(ext,indent=2),file=sys.stderr)
    print("^^^^^^^^^",file=sys.stderr)
    print("EXTENSION",file=sys.stderr)

    core = merge_ext_to_core(core, ext)
    
    #debug
    print("OUTPUT",file=sys.stderr)
    print("vvvvvv",file=sys.stderr)
    print(json.dumps(core,sort_keys=False,indent=2),file=sys.stderr)
    print("^^^^^^",file=sys.stderr)
    print("OUTPUT",file=sys.stderr)

    # the resulting YAML
    print(dump(core,sort_keys=False))

if __name__ == "__main__":
    main()