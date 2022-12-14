#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@Description:       : this file contains all codes that parse xml files of CWE and generate flaw and fix labels list.
like this :
[
    {
        'flaw':{
            'file_path':'/xxx/xx/xx/x/xx.c',
            'line':10
        },
        'fix':{
            'file_path':'/xxx/xx/xx/x/xx.c',
            'line':10
        }
    }
]

the start function is get_all_label_list

@Date     :2021/08/21 20:35:59
@Author      :ives-nx
@version      :1.0
'''
from typing import List, Dict, Set
import os
import xml.etree.ElementTree as ET
import numpy

from scipy.sparse.construct import random
from utils.common import CWEID_ADOPT
from utils.git_checkout import checkout_to, checkout_back, checkout_to_pre
import shutil
import re

def get_pair_testcase():
    """
    @description  : filter all pair testcase from whole xml
    ---------
    @param  :
    -------
    @Returns  : pair testcases tree
    -------
    """
    
    
    xmlPath = os.path.join('/home/niexu/dataset/CWES/CWE119/source-code', "manifest.xml")
    tree = ET.ElementTree(file=xmlPath)
    testcases = tree.findall('testcase')
    root =ET.Element('container')
    for testcase in testcases:
        associations = testcase.findall('association')
        flag = False
        for association in associations:
            if association.attrib['type'] == 'pair':
                flag = True
        if flag:
            root.append(testcase)
    print(len(root))
    pair_tree = ET.ElementTree(root)
    return pair_tree
    # mixed_tree.write(os.path.join('/home/niexu/dataset/CWES/CWE119/source-code', "pair_manifest.xml"), encoding='utf8')

def get_mixed_testcase():
    """
    @description  : filter all mixed testcase from whole xml
    ---------
    @param  :
    -------
    @Returns  : mixed testcases tree
    -------
    """
    
    
    xmlPath = os.path.join('/home/niexu/dataset/CWES/CWE119/source-code', "manifest.xml")
    tree = ET.ElementTree(file=xmlPath)
    testcases = tree.findall('testcase')
    root =ET.Element('container')
    
    for testcase in testcases:
        files = testcase.findall('file')
        m_flag = False
        for f in files:
            mixeds = f.findall('mixed')
            if mixeds != []:
                m_flag = True
        if m_flag:
            root.append(testcase)
    print(len(root))
    mixed_tree = ET.ElementTree(root)
    return mixed_tree
    # mixed_tree.write(os.path.join('/home/niexu/dataset/CWES/CWE119/source-code', "mixed_manifest.xml"), encoding='utf8')

def get_other_testcase():
    """
    @description  : filter other testcase from whole xml, except pair and mixed
    ---------
    @param  :
    -------
    @Returns  : other testcases tree
    -------
    """
    
    

    xmlPath = os.path.join('/home/niexu/dataset/CWES/CWE119/source-code', "manifest.xml")
    tree = ET.ElementTree(file=xmlPath)
    testcases = tree.findall('testcase')
    root =ET.Element('container')
    
    for testcase in testcases:
        associations = testcase.findall('association')
        flag = False
        for association in associations:
            if association.attrib['type'] == 'pair':
                flag = True
        if flag:
            continue
        files = testcase.findall('file')
        m_flag = False
        for f in files:
            mixeds = f.findall('mixed')
            if mixeds != []:
                m_flag = True
        if m_flag:
           continue
        root.append(testcase)
    print(len(root))
    other_tree = ET.ElementTree(root)
    return other_tree
    # mixed_tree.write(os.path.join('/home/niexu/dataset/CWES/CWE119/source-code', "other_manifest.xml"), encoding='utf8')

def parse_mixed_testcase(et:ET.ElementTree):
    """
    @description  : parse mixed testcase and generate fix and flaw pairs.
    ---------
    @param  : mixed label list
    -------
    @Returns  :
    -------
    """
    
    
    IGNORE = ['119-7600-c', '119-7700-c']
    label_dict = dict()
    testcases = et.findall('testcase')
    for testcase in testcases:
        testcase_id = testcase.attrib['id']
        files = testcase.findall('file')
        label_dict[testcase_id] = dict()
        for file in files:
            path = file.attrib['path']
            # print(path)
            mixed = file.findall('mixed')
            if mixed != []:
                vul_line = set()
                for mix in mixed:
                    line = mix.attrib['line']
                    vul_line.add(int(line))
                vul_line = list(vul_line)
                vul_line.sort()
                # ???????????????flaw ??? ?????? IGNORE ???????????? bug

                if len(vul_line) > 1 and path.split('/')[0] in IGNORE:
                    continue
                
                
                file_path = os.path.join('/home/niexu/dataset/CWES/CWE119/source-code', path)
                fix_lines = find_fix_lines(file_path=file_path)
                fix_lines = list(fix_lines)
                fix_lines.sort()

                if vul_line != [] and fix_lines != []:
                    label_dict[testcase_id][path] = dict()
                    label_dict[testcase_id][path]['vul_line'] = vul_line
                    label_dict[testcase_id][path]['fix_line'] = fix_lines
    mixed_label_list = list()
    for testcase_id in label_dict:
        test = label_dict[testcase_id]
        for path in test:
            vul_lines = test[path]['vul_line']
            fix_lines = test[path]['fix_line']
            info = dict()
            info['path'] = path
            info['vul_line'] = vul_lines
            info['fix_line'] = fix_lines
            info['form'] = 'mixed'
            mixed_label_list.append(info)
    #         for vul_line in vul_lines:
    #             info = dict()
    #             flaw_info = dict()
    #             fix_info = dict()
    #             fix_line = numpy.random.choice(fix_lines, 1, replace=False)[0]
    #             flaw_info['path'] = path
    #             flaw_info['line'] = vul_line
    #             fix_info['path'] = path
    #             fix_info['line'] = int(fix_line)
    #             info['flaw'] = flaw_info
    #             info['fix'] = fix_info
    #             mixed_label_list.append(info)
    return  mixed_label_list



def get_file_content(file_path):
    """
    @description  : get file content lines
    ---------
    @param  : 
    -------
    @Returns  :
    -------
    """
    
    
    file_content = []
    with open(file_path, 'r', encoding='utf8') as f:
        file_content = f.readlines()
    return file_content


def find_fix_lines(file_path):
    """
    @description  : find fix line number from mixed testcase.
    ---------
    @param  : 
    -------
    @Returns  : fix lines 
    -------
    """
    
    
    file_content = get_file_content(file_path=file_path)
    fix_lines = set()
    str_start = '/* FIX:'
    str_end = '*/'
    # start_pattern = re.compile(str_start)
    # end_parttern = re.compile(str_end)
    start_flag = False
    end_flag = False

    for idx, line in enumerate(file_content, start=1):
        if str_start in line and str_end in line:
            start_flag = True
            end_flag  = True
        elif str_start in line and str_end not in line:
            start_flag = True
        elif start_flag and str_end in line :
            end_flag  = True
        else:
            continue
        if start_flag and end_flag:
            fix_lines.add(idx+1)
            start_flag = False
            end_flag = False
    return fix_lines


def parse_pair_tree(et:ET.ElementTree):
    """
    @description  : parse pair testcases and generate fix and flaw pairs.
    ---------
    @param  :   pair testcases tree
    -------
    @Returns  : 
    -------
    """
    
    
    flaw_dict = dict()
    fix_dict = dict()
    testcases = et.findall('testcase')
    for testcase in testcases:
        testcase_id = testcase.attrib['id']
        files = testcase.findall('file')
        associations = testcase.findall('association')
        for association in associations:
            if association.attrib['type'] == 'pair':
                pair_testcase_id = association.attrib['testcaseid']
        flaw_flag = False
        fix_flag = False
        flag = False
        for file in files:
            path = file.attrib['path']
            # print(path)
            flaws = file.findall('flaw')

            fixes = file.findall('fix')

            if flaws != [] and flaws:
                flaw_flag = True
            if fixes != []:
                fix_flag = True
            if flaw_flag and fix_flag:
                #????????????fix ??? ??? flaw ???testcase
                flag = True
                break
            if fix_flag and len(fixes) > 1 :
                #?????? ?????????flaw???testcase
                flag = True
                break
            if flaw_flag and len(flaws) > 1:
                #?????? ?????????fix???testcase
                flag = True
                break
        if not flag: 
            for file in files:
                path = file.attrib['path']
                # print(path)
                flaws = file.findall('flaw')

                fixes = file.findall('fix')

                if flaws != [] and fixes == []:
                    flaw_info = dict()
                    flaw_info['pair_testcase_id'] = pair_testcase_id
                    flaw_info['path'] = path
                    flaw_info['line'] = int(flaws[0].attrib['line'])
                    flaw_info['type'] = 'flaw'
                    if testcase_id not in flaw_dict.keys():
                        flaw_dict[testcase_id] = list()
                        flaw_dict[testcase_id].append(flaw_info)
                    else:
                        
                        flaw_dict[testcase_id].append(flaw_info)

                if fixes != [] and flaws == []:
                    fix_info = dict()
                    fix_info['path'] = path
                    fix_info['line'] = int(fixes[0].attrib['line'])
                    fix_info['type'] = 'fix'
                    if testcase_id not in fix_dict.keys():
                        fix_dict[testcase_id] = list()
                        fix_dict[testcase_id].append(fix_info)
                    else:
                        
                        fix_dict[testcase_id].append(fix_info)
    return flaw_dict, fix_dict 

def get_pair_label_list(et:ET.ElementTree):
    """
    @description  :  generate bug pairs from pair testcase
    ---------
    @param  : et: pair testcases tree
    -------
    @Returns  :
    -------
    """
    
    
    flaw_dict, fix_dict = parse_pair_tree(et)
    label_pair_list = list()
    
    for id in flaw_dict:
        for idx,flaw in enumerate(flaw_dict[id]):
            info = dict()
            pair_testcase_id = flaw['pair_testcase_id']
            if pair_testcase_id not in fix_dict.keys():
                continue
            flaw_info = dict()
            flaw_info['path'] = flaw['path']
            flaw_info['line'] = flaw['line']
            fix_info = dict()
            fix_info['path'] = fix_dict[pair_testcase_id][idx]['path']
            fix_info['line'] = fix_dict[pair_testcase_id][idx]['line']
            info['flaw'] = flaw_info
            info['fix'] = fix_info
            info['form'] = 'pair'
            label_pair_list.append(info)
    
    return label_pair_list


def get_all_label_list():
    """
    @description  : merge pair label list and mixed label list
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    all_label_list = list()
    pair_tree = get_pair_testcase()
    pair_label_list = get_pair_label_list(et=pair_tree)

    mixed_tree = get_mixed_testcase()
    mixed_label_list = parse_mixed_testcase(et = mixed_tree)
    all_label_list.extend(pair_label_list)
    all_label_list.extend(mixed_label_list)
  
    return all_label_list

def get_sard_vul_info_list(cwe_id):
    """
    @description  : [
        {
            "path":"",
            "line":line
        }
    ]
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    vul_info_list = list()
    xmlPath = os.path.join('/home/niexu/dataset/CWES/{}/source-code'.format(cwe_id), "manifest.xml")
    tree = ET.ElementTree(file=xmlPath)
    testcases = tree.findall('testcase')
    for testcase in testcases:
        files = testcase.findall("file")
        testcaseid = testcase.attrib["id"]

        for file in files:
            path = file.attrib["path"]
            flaws = file.findall("flaw")
            mixeds = file.findall("mixed")
            fix = file.findall("fix")
            # print(mixeds)
            VulLine = set()
            if (flaws != [] or mixeds != [] or fix != []):
                # targetFilePath = path
                if (flaws != []):
                    for flaw in flaws:
                        VulLine.add(int(flaw.attrib["line"]))
                if (mixeds != []):
                    for mixed in mixeds:
                        VulLine.add(int(mixed.attrib["line"]))
            info = dict()
            info['path'] = path
            info['line'] = list(VulLine)
            vul_info_list.append(info)

    return vul_info_list