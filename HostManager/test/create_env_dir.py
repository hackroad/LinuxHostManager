#!/usr/bin/env python

# -*- encoding: utf-8 -*-

__author__ = 'yuanwm <ywmpsn@163.com>'

import os
import shutil

'''
/account/ -生产程序目录

        tools/  -
        cfg/    -配置文件目录
                xxx/    -xxx程序配置文件目录
        dll/    -动态库目录
                xxx/    -xxx程序动态库目录
        bin/    -程序执行码目录
                xxx     -xxx程序执行文件
        xbin/   -程序运行执行码目录(从bin目录拷贝运行的执行码)
                X_xxx   -xxx程序运行的执行码X_xxx
        script/ -脚本目录
                xxx/    -xxx程序脚本

/actwork/ -个人工作文件目录
        xxx/    -xxx代表用户名字简称-如:yuanwm

/actdata/ -程序数据目录
    script_data/    -脚本数据目录
        xxx/    -xxx脚本
    app_data/   -程序数据目录
        xxx/    -xxx应用

/actlog/ -程序日志目录
    script_log/    -脚本日志目录
        xxx/    -xxx脚本
    app_log/   -程序日志目录
        xxx/    -xxx应用
/actsrc/ -应用/脚本源码目录
    script/    -脚本目录
        xxx/    -xxx脚本
    app/   -程序目录
        xxx/    -xxx应用
'''

# 目录字典:
"""
note 为说明; IsCreate: 1为创建 0: 为不创建
"""
env_directory_dict = {
    "account": {
        "note": "生产程序目录",
        "IsCreate": 1,
        "SubDir": {
            "note": "子目录",
            "IsCreate": 0,
            "tools": {
                "note": "工具目录,存放各类生产工具",
                "IsCreate": 1,
                "public":{
                    "note": "公共工具目录",
                    "IsCreate": 1,
                }
            },
            "cfg": {
                "note": "程序配置文件目录",
                "IsCreate": 1,
                "public":{
                    "note": "公共配置目录",
                    "IsCreate": 1,
                }
            },
            "dll": {
                "note": "程序动态库文件目录",
                "IsCreate": 1,
                "public": {
                    "note": "公共动态库目录",
                    "IsCreate": 1,
                }
            },
            "bin": {
                "note": "程序链接后执行文件目录",
                "IsCreate": 1,
            },
            "xbin": {
                "note": "程序启动执行文件目录",
                "IsCreate": 1,
            },
            "script": {
                "note": "脚本目录",
                "IsCreate": 1,
                "public": {
                    "note": "公共脚本目录",
                    "IsCreate": 1,
                }
            }
        }
    },
    "actwork": {
        "note": "个人工作目录",
        "IsCreate": 1
    },
    "actdata": {
        "note": "数据目录",
        "IsCreate": 1,
        "SubDir": {
            "note": "子目录",
            "IsCreate": 0,
            "script_data": {
                "note": "脚本数据目录",
                "IsCreate": 1
            },
            "app_data": {
                "note": "应用数据目录",
                "IsCreate": 1
            }
        }
    },
    "actlog": {
        "note": "日志目录",
        "IsCreate": 1,
        "SubDir": {
            "note": "子目录",
            "IsCreate": 0,
            "script_log": {
                "note": "脚本日志目录",
                "IsCreate": 1
            },
            "app_log": {
                "note": "应用日志目录",
                "IsCreate": 1
            }
        }
    },
    "actsrc": {
        "note": "源码目录(编译/链接目录)",
        "IsCreate": 1,
        "SubDir": {
            "note": "子目录",
            "IsCreate": 0,
            "script": {
                "note": "脚本目录",
                "IsCreate": 1
            },
            "app": {
                "note": "应用目录",
                "IsCreate": 1,
            }
        }
    }
}


def traver_dict(in_dict, opera_flag, up_dir="", up_key=""):
    """根据定义的字典，创建目录
    不存在创建，存在不作操作
    in_dict: 传入目录定义字典   up_dir：上一级目录,不带"/"  oper_flag: Create 创建 Delete 删除
    """

    # 非字典直接返回即可
    if not isinstance(in_dict, dict):
        return True

    # 判断是否创建上级目录
    if "IsCreate" in in_dict:
        if in_dict['IsCreate'] == 1:
            up_dir = up_dir + os.path.sep + up_key
            if opera_flag == "Create":
                print("创建目录:[%s]" % up_dir, end='')
                os.makedirs(up_dir, exist_ok=True)
            elif opera_flag == "Remove":
                print("删除目录:[%s]" % up_dir, end='')
                shutil.rmtree(up_dir, ignore_errors=True)
            # 输出目录含义
            if "note" in in_dict:
                print("------>>>[%s]" % in_dict['note'])
            else:
                print("")

    # 有子目录的存在
    for key, value in in_dict.items():
        # 如果是字典, 组合新目录名称
        if isinstance(value, dict):
            traver_dict(in_dict=value, up_dir=up_dir, up_key=key,opera_flag=opera_flag)

    return True


if __name__ == "__main__":
    # 这里up_dir=""代表的是'/' 跟目录; oper_flag Create:创建  Remove: 删除
    traver_dict(env_directory_dict, up_dir="", opera_flag="Create")
