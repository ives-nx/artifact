import json
import random
def write_json(json_dict, output):
    with open(output, 'w', encoding='utf8') as f:
        json.dump(json_dict,f,indent=2)
        f.close()

def read_json(path):
    json_dict = []
    with open(path, 'r', encoding='utf8') as f:
        
        json_dict = json.load(f)
        f.close()
    return json_dict

def get_data_json(data_path):
    random.seed(7)
    with open(data_path,'r',encoding = 'utf8') as f:
        data_json = json.load(f)
        f.close()
    random.shuffle(data_json)
    for idx,xfg in enumerate(data_json, start=0):
        xfg['xfg_id'] = idx
        xfg['flip'] = False
    return data_json