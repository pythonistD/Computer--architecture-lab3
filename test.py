import yaml

with open('golden/hello_user_name.yml') as f:
    y_f = yaml.safe_load(f.read())
    print(y_f['in_source'])