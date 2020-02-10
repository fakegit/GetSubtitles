# coding: utf-8

import os
from os import path
from collections import OrderedDict

from getsub.constants import *


def get_videos(raw_path, store_path=""):
    """
    传入视频名称或路径，构造一个包含视频路径和是否存在字幕信息的字典返回
    若指定 store_path ，则是否存在字幕会在 store_path 中查找

    params:
        raw_path: str, video path/name or a directory path
        store_path: str, subtitles store path
    return:
        video_dict: dict
            key: video file name, without path
            value: "video_path" - str, abspath of video's parent directory
                   "store_path" - str, subtitles' store path (abspath)
                   "has_subtitle" - bool
    """

    raw_path = raw_path.replace('"', "")
    store_path = store_path.replace('"', "")
    if store_path:
        store_path = path.abspath(store_path)
    store_path_files = []

    if not path.isdir(store_path):
        if store_path:
            print("store path is invalid: " + store_path)
        store_path = ""
    else:
        print("subtitles will be saved to: " + store_path)
        for root, dirs, files in os.walk(store_path):
            store_path_files.extend(files)

    video_dict = OrderedDict()

    if path.isdir(raw_path):  # directory
        for root, dirs, files in os.walk(raw_path):
            if not store_path:
                store_path_files = files
            for file in files:
                v_name, v_type = path.splitext(file)
                if v_type not in VIDEO_FORMATS:
                    continue
                sub_exists = False
                for sub_type in SUB_FORMATS:
                    if v_name + sub_type in store_path_files:
                        sub_exists = True
                        break
                    elif v_name + ".zh" + sub_type in store_path_files:
                        # plex
                        sub_exists = True
                        break
                video_dict[file] = {
                    "video_path": path.abspath(root),
                    "store_path": path.abspath(root)
                    if not store_path
                    else store_path,
                    "has_subtitle": sub_exists,
                }
    elif path.isabs(raw_path):  # video's absolute path
        v_path, v_raw_name = path.split(raw_path)
        v_name = path.splitext(v_raw_name)[0]
        s_path = v_path if not store_path else store_path
        sub_exists = False
        for sub_type in SUB_FORMATS:
            if path.exists(path.join(s_path, v_name + sub_type)):
                sub_exists = True
                break
            elif path.exists(path.join(s_path, v_name + ".zh" + sub_type)):
                # plex
                sub_exists = True
                break
        video_dict[v_raw_name] = {
            "video_path": v_path,
            "store_path": s_path,
            "has_subtitle": sub_exists,
        }
    else:  # single video name, no path
        s_path = os.getcwd() if not store_path else store_path
        video_dict[raw_path] = {
            "video_path": raw_path,
            "store_path": s_path,
            "has_subtitle": False,
        }

    return video_dict
