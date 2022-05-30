import sys
sys.path.append('..')
from utils.json_ops import read_json, write_json
import numpy as np
import os

def analysis_txt(path):
    
    with open(path, 'r') as f:
        all_str = f.read()
        f.close()
    xfg_ids = all_str.split(',')[:-1]
    
    xfg_id_dict = dict()
    for xfg_id in xfg_ids:
        if xfg_id not in xfg_id_dict.keys():
            xfg_id_dict[xfg_id] = 1
        else:
            xfg_id_dict[xfg_id] += 1
    sortd_id_dict = sorted(xfg_id_dict.items(), key=lambda item:item[1], reverse=True)
    print(len(xfg_id_dict))
    # print(sortd_id_dict)
    # return sortd_id_dict
    return xfg_ids

if __name__ == "__main__":
    train_txt_path = 'train_false_xfg_ids.txt'
    val_txt_path = 'val_false_xfg_ids.txt'
    test_true_txt_path = 'test_true_xfg_ids.txt'
    test_false_txt_path = 'test_false_xfg_ids.txt'

    test_true = set(analysis_txt(test_true_txt_path))
    test_false = set(analysis_txt(test_false_txt_path))

    tmp = [int(i) for i in list(test_false & test_true) ]

    write_json(tmp, 'rm_test_xfg_ids.json')
    # sorted_train_xfg_id = analysis_txt(train_txt_path)
    # xfg_ids = []
    # for info in sorted_train_xfg_id:
    #     if info[1] >= 40:
    #         xfg_ids.append(int(info[0]))
    # # print(len(xfg_ids))
    # noise_xfg_ids = set(read_json('noise_xfg_ids.json'))
    # found_xfg_ids = set(read_json('found_xfg_ids.json'))
    # found_dif_noise = list(found_xfg_ids - noise_xfg_ids)
    
    # may_false_ids = list(set(xfg_ids) - set(found_dif_noise))
    
    # CWE119 = read_json('CWE119.json')

    # npdata = np.array(CWE119)

    # write_json(npdata[may_false_ids].tolist(), 'may_false_xfgs.json')