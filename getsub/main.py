# coding: utf-8

import os
import re
import sys
import zipfile
import rarfile
import argparse
from io import BytesIO
from collections import OrderedDict as order_dict
from traceback import format_exc

import chardet
from guessit import guessit
from requests import exceptions
from requests.utils import quote

from getsub.__version__ import __version__
from getsub.sys_global_var import prefix
from getsub.py7z import Py7z
from getsub.downloader import DownloaderManager


class GetSubtitles(object):

    if sys.stdout.encoding == 'cp936':
        output_encode = 'gbk'
    else:
        output_encode = 'utf8'

    def __init__(self, name, query, single,
                 more, both, over, plex, debug, sub_num, downloader, sub_path):
        self.video_format_list = ['.webm', '.mkv', '.flv', '.vob', '.ogv',
                                  '.ogg', '.drc', '.gif', '.gifv', '.mng',
                                  '.avi', '.mov', '.qt', '.wmv', '.yuv',
                                  '.rm', '.rmvb', '.asf', '.amv', '.mp4',
                                  '.m4p', '.m4v', 'mpg', '.mp2', '.mpeg',
                                  '.mpe', '.mpv', '.mpg', '.m2v', '.svi',
                                  '.3gp', '.3g2', '.mxf', '.roq', '.nsv',
                                  '.flv', '.f4v', '.f4p', '.f4a', '.f4b']
        self.sub_format_list = ['.ass', '.srt', '.ssa', '.sub']
        self.support_file_list = ['.zip', '.rar', '.7z']
        self.arg_name = name
        self.sub_store_path = sub_path
        self.both = both
        self.query, self.single = query, single
        self.more, self.over = more, over
        if not sub_num:
            self.sub_num = 5
        else:
            self.sub_num = int(sub_num)
        self.plex = plex
        self.debug = debug
        self.s_error = ''
        self.f_error = ''
        if not downloader:
            self.downloader = DownloaderManager.downloaders
        else:
            if downloader not in DownloaderManager.downloader_names:
                print("\nNO SUCH DOWNLOADER:", "PLEASE CHOOSE FROM",
                      ', '.join(DownloaderManager.downloader_names), '\n')
                sys.exit(1)
            self.downloader = [
                DownloaderManager.get_downloader_by_name(downloader)]
        self.failed_list = []  # [{'name', 'path', 'error', 'trace_back'}

    def get_path_name(self, args, args1):
        """ 传入输入的视频名称或路径,
            构造一个包含视频路径和是否存在字幕信息的字典返回。
            video_dict: {'path': path, 'have_subtitle': sub_exists} """

        mix_str = args.replace('"', '')
        if args1:
            store_path = args1.replace('"', '')
        else:
            store_path = ''
        store_path_files = []
        if not os.path.isdir(store_path):
            print('no valid path specfied,download sub file to video file location.')
            store_path = ''
        else:
            for root, dirs, files in os.walk(store_path):
                store_path_files.extend(files)
        video_dict = order_dict()
        if os.path.isdir(mix_str):  # 一个文件夹
            for root, dirs, files in os.walk(mix_str):
                for one_name in files:
                    suffix = os.path.splitext(one_name)[1]
                    # 检查后缀是否为视频格式
                    if suffix not in self.video_format_list:
                        continue
                    v_name_no_format = os.path.splitext(one_name)[0]
                    sub_exists = max(
                        list(
                            map(
                                lambda sub_type:
                                    int(v_name_no_format + sub_type in files + store_path_files
                                        or v_name_no_format + '.zh' + sub_type in files + store_path_files),
                                    self.sub_format_list
                            )
                        )
                    )
                    video_dict[one_name] = {'path': next(item for item in [store_path, os.path.abspath(root)] if item != ''),
                                            'have_subtitle': sub_exists}

        elif os.path.isabs(mix_str):  # 视频绝对路径
            v_path, v_name = os.path.split(mix_str)
            v_name_no_format = os.path.splitext(v_name)[0]
            if os.path.isdir(store_path):
                s_path = os.path.abspath(store_path)
            else:
                s_path = v_path
            sub_exists = max(
                list(
                    map(
                        lambda sub_type:
                            os.path.exists(
                                os.path.join(s_path, v_name_no_format+sub_type)
                            ),
                            self.sub_format_list
                    )
                )
            )
            video_dict[v_name] = {'path': s_path,
                                  'have_subtitle': sub_exists}
        else:  # 单个视频名字，无路径
            if not os.path.isdir(store_path):
                video_dict[mix_str] = {'path': os.getcwd(), 'have_subtitle': 0}
            else:
                video_dict[mix_str] = {'path': os.path.abspath(
                    store_path), 'have_subtitle': 0}
        return video_dict

    def choose_subtitle(self, sub_dict):
        """ 传入候选字幕字典
            若为查询模式返回选择的字幕包名称，字幕包下载地址
            否则返回字幕字典第一个字幕包的名称，字幕包下载地址 """

        exit = False

        if not self.query:
            chosen_sub = list(sub_dict.keys())[0]
            link = sub_dict[chosen_sub]['link']
            session = sub_dict[chosen_sub].get('session', None)
            return exit, [[chosen_sub, link, session]]

        print(prefix, '%3s)  Exit. Not downloading any subtitles.' % 0)
        for i, key in enumerate(sub_dict.keys()):
            if i == self.sub_num:
                break
            lang_info = ''
            lang_info += '【简】' if 4 & sub_dict[key]['lan'] else '      '
            lang_info += '【繁】' if 2 & sub_dict[key]['lan'] else '      '
            lang_info += '【英】' if 1 & sub_dict[key]['lan'] else '      '
            lang_info += '【双】' if 8 & sub_dict[key]['lan'] else '      '
            a_sub_info = ' %3s) %s  %s' % (i + 1, lang_info, key)
            a_sub_info = prefix + a_sub_info
            print(a_sub_info)

        indexes = range(len(sub_dict.keys()))
        choices = None
        chosen_subs = []
        while not choices:
            try:
                print(prefix)
                choices = input(prefix + '  choose subtitle: ')
                choices = [int(c) for c in re.split(',|，', choices)]
            except ValueError:
                print(prefix + '  Error: only numbers accepted')
                continue
            if 0 in choices:
                exit = True
                return exit, []
            for choice in choices:
                if not choice - 1 in indexes:
                    print(prefix +
                          '  Error: choice %d not within the range' % choice)
                    choices.remove(choice)
                else:
                    chosen_sub = list(sub_dict.keys())[choice - 1]
                    link = sub_dict[chosen_sub]['link']
                    session = sub_dict[chosen_sub].get('session', None)
                    chosen_subs.append([chosen_sub, link, session])
        return exit, chosen_subs

    def guess_subtitle(self, sublist, video_info):
        """ 传入压缩包字幕列表，视频信息，返回最佳字幕名称。
            若没有符合字幕，查询模式下返回第一条字幕， 否则返回None """

        if not sublist:
            print(prefix + ' warn: ' + 'no subtitle in this archive')
            return None

        video_name = video_info['title'].lower()
        season = str(video_info.get('season'))
        episode = str(video_info.get('episode'))
        year = str(video_info.get('year'))
        vtype = str(video_info.get('type'))

        score = []
        for one_sub in sublist:
            one_sub = one_sub.lower()
            score.append(0)  # 字幕起始分数

            if one_sub[-1] == '/':  # 压缩包内文件夹，跳过
                continue

            one_sub = os.path.split(one_sub)[-1]  # 提取文件名
            try:
                # zipfile:/Lib/zipfile.py:1211 Historical ZIP filename encoding
                # try cp437 encoding
                one_sub = one_sub.encode('cp437').decode('gbk')
            except:
                pass
            sub_name_info = guessit(one_sub)
            if sub_name_info.get('title'):
                sub_title = sub_name_info['title'].lower()
            else:
                sub_title = ''
            sub_season = str(sub_name_info.get('season'))
            sub_episode = str(sub_name_info.get('episode'))
            sub_year = str(sub_name_info.get('year'))

            if vtype == 'movie' and year != sub_year:
                # 电影年份不匹配
                continue

            if video_name == sub_title:
                if not (season == sub_season and episode == sub_episode):
                    continue  # 名字匹配，剧集不匹配
                else:
                    score[-1] += 2  # 名字剧集都匹配
            elif season == sub_season and episode == sub_episode:
                score[-1] += 2  # 名字不匹配，剧集匹配
            else:
                score[-1] -= 2
                continue  # 名字剧集都不匹配

            if '简体' in one_sub or 'chs' in one_sub or '.gb.' in one_sub:
                score[-1] += 5
            if '繁体' in one_sub or 'cht' in one_sub or '.big5.' in one_sub:
                score[-1] += 3
            if 'chs.eng' in one_sub or 'chs&eng' in one_sub:
                score[-1] += 7
            if '中英' in one_sub or '简英' in one_sub or '双语' in one_sub or '简体&英文' in one_sub:
                score[-1] += 9

            score[-1] += ('ass' in one_sub or 'ssa' in one_sub) * 2
            score[-1] += ('srt' in one_sub) * 1

        max_score = max(score)
        if max_score <= 0 and not self.query:
            return None
        max_pos = score.index(max_score)

        return sublist[max_pos]

    def get_file_list(self, file_handler):
        """ 传入一个压缩文件控制对象，读取对应压缩文件内文件列表。
            返回 {one_sub: file_handler} """

        sub_lists_dict = dict()
        for one_file in file_handler.namelist():

            if one_file[-1] == '/':
                continue
            if os.path.splitext(one_file)[-1] in self.sub_format_list:
                sub_lists_dict[one_file] = file_handler
                continue

            if os.path.splitext(one_file)[-1] in self.support_file_list:
                sub_buff = BytesIO(file_handler.read(one_file))
                datatype = os.path.splitext(one_file)[-1]
                if datatype == '.zip':
                    sub_file_handler = zipfile.ZipFile(sub_buff, mode='r')
                elif datatype == '.rar':
                    sub_file_handler = rarfile.RarFile(sub_buff, mode='r')
                elif datatype == '.7z':
                    sub_file_handler = Py7z(sub_buff)
                sub_lists_dict.update(self.get_file_list(sub_file_handler))

        return sub_lists_dict

    def extract_subtitle(self, v_name, v_path, archive_name,
                         datatype, sub_data_b, rename,
                         single, both, plex, delete=True):
        """ 接受下载好的字幕包字节数据， 猜测字幕并解压。 """

        v_info_d = guessit(v_name)

        sub_buff = BytesIO()
        sub_buff.write(sub_data_b)

        if datatype == '.7z':
            try:
                sub_buff.seek(0)
                file_handler = Py7z(sub_buff)
            except:
                # try with zipfile
                datatype = '.zip'
        if datatype == '.zip':
            try:
                sub_buff.seek(0)
                file_handler = zipfile.ZipFile(sub_buff, mode='r')
            except:
                # try with rarfile
                datatype = '.rar'
        if datatype == '.rar':
            sub_buff.seek(0)
            file_handler = rarfile.RarFile(sub_buff, mode='r')

        sub_lists_dict = dict()
        sub_lists_dict.update(self.get_file_list(file_handler))

        # sub_lists = [x for x in file_handler.namelist() if x[-1] != '/']

        if not single:
            sub_name = self.guess_subtitle(
                list(sub_lists_dict.keys()), v_info_d)
        else:
            print(prefix)
            for i, single_subtitle in enumerate(sub_lists_dict.keys()):
                single_subtitle = single_subtitle.split('/')[-1]
                try:
                    # zipfile: Historical ZIP filename encoding
                    # try cp437 encoding
                    single_subtitle = single_subtitle.\
                        encode('cp437').decode('gbk')
                except:
                    pass
                info = ' %3s)  %s' % (str(i+1), single_subtitle)
                print(prefix + info)

            indexes = range(len(sub_lists_dict.keys()))
            choice = None
            while not choice:
                try:
                    print(prefix)
                    choice = int(input(prefix + '  choose subtitle: '))
                except ValueError:
                    print(prefix + '  Error: only numbers accepted')
                    continue
                if not choice - 1 in indexes:
                    print(prefix + '  Error: numbers not within the range')
                    choice = None
            sub_name = list(sub_lists_dict.keys())[choice - 1]

        if not sub_name:  # 自动模式下无最佳猜测
            return None

        os.chdir(v_path)  # 切换到视频所在文件夹

        v_name_without_format = os.path.splitext(v_name)[0]
        # video_name + sub_type
        to_extract_types = []
        sub_title, sub_type = os.path.splitext(sub_name)
        to_extract_subs = [[sub_name, sub_type]]
        if both:
            another_sub_type = '.srt' if sub_type == '.ass' else '.ass'
            another_sub = sub_name.replace(sub_type, another_sub_type)
            if another_sub in list(sub_lists_dict.keys()):
                to_extract_subs.append([another_sub, another_sub_type])
            else:
                print(prefix +
                      ' no %s subtitles in this archive' % another_sub_type)

        if delete:
            for one_sub_type in self.sub_format_list:  # 删除若已经存在的字幕
                if os.path.exists(v_name_without_format + one_sub_type):
                    os.remove(v_name_without_format + one_sub_type)
                if os.path.exists(v_name_without_format + '.zh' + one_sub_type):
                    os.remove(v_name_without_format + '.zh' + one_sub_type)

        for one_sub, one_sub_type in to_extract_subs:
            if rename:
                if plex:
                    sub_new_name = v_name_without_format + '.zh' + one_sub_type
                else:
                    sub_new_name = v_name_without_format + one_sub_type
            else:
                sub_new_name = one_sub
            with open(sub_new_name, 'wb') as sub:  # 保存字幕
                file_handler = sub_lists_dict[one_sub]
                sub.write(file_handler.read(one_sub))

        if self.more:  # 保存原字幕压缩包
            if rename:
                archive_new_name = v_name_without_format + datatype
            else:
                archive_new_name = archive_name + datatype
            with open(archive_new_name, 'wb') as f:
                f.write(sub_data_b)
            print(prefix + ' save original file.')

        return to_extract_subs

    def process_archive(self, one_video, video_info,
                        sub_choice, link, session, rename=True, delete=True):
        """ 解压字幕包，返回字幕包中字幕名列表

            Return:
                message: str, 无其它错误则为空
                extract_sub_names: list
        """
        message = ''
        if self.query:
            print(prefix + ' ')
        choice_prefix = sub_choice[:sub_choice.find(']') + 1]
        datatype, sub_data_bytes, err_msg = DownloaderManager.get_downloader_by_choice_prefix(
            choice_prefix).download_file(sub_choice, link, session=session)
        if err_msg:
            return err_msg, None
        extract_sub_names = []
        if datatype not in self.support_file_list:
            # 不支持的压缩包类型
            message = 'unsupported file type ' + datatype
            return message, None
        # 获得猜测字幕名称
        # 查询模式必有返回值，自动模式无猜测值返回None
        extract_sub_names = self.extract_subtitle(
            one_video, video_info['path'],
            sub_choice, datatype, sub_data_bytes,
            rename, self.single, self.both, self.plex, delete=delete
        )
        if not extract_sub_names:
            return message, None
        for extract_sub_name, extract_sub_type in extract_sub_names:
            extract_sub_name = extract_sub_name.split('/')[-1]
            try:
                # zipfile: Historical ZIP filename encoding
                # try cp437 encoding
                extract_sub_name = extract_sub_name. \
                    encode('cp437').decode('gbk')
            except:
                pass
            try:
                print(prefix + ' ' + extract_sub_name)
            except UnicodeDecodeError:
                print(prefix + ' '
                      + extract_sub_name.encode('gbk'))
        return message, extract_sub_names

    def start(self):

        all_video_dict = self.get_path_name(self.arg_name, self.sub_store_path)

        for one_video, video_info in all_video_dict.items():

            self.s_error = ''  # 重置错误记录
            self.f_error = ''

            try:
                print('\n' + prefix + ' ' + one_video)  # 打印当前视频及其路径
                print(prefix + ' ' + video_info['path'] + '\n' + prefix)

                if video_info['have_subtitle'] and not self.over:
                    print(prefix
                          + " subtitle already exists, add '-o' to replace it.")
                    continue

                sub_dict = order_dict()
                for i, downloader in enumerate(self.downloader):
                    try:
                        sub_dict.update(
                            downloader.get_subtitles(one_video, sub_num=self.sub_num)
                        )
                    except ValueError as e:
                        if str(e) == 'Zimuku搜索结果出现未知结构页面':
                            print(prefix + ' warn: ' + str(e))
                        else:
                            raise(e)
                    except (exceptions.Timeout, exceptions.ConnectionError):
                        print(prefix + ' connect timeout, search next site.')
                        if i < (len(self.downloader)-1):
                            continue
                        else:
                            print(prefix + ' PLEASE CHECK YOUR NETWORK STATUS')
                            sys.exit(0)
                    if len(sub_dict) >= self.sub_num:
                        break
                if len(sub_dict) == 0:
                    self.s_error += 'no search results. '
                    continue

                extract_sub_names = []
                # 遍历字幕包直到有猜测字幕
                while not extract_sub_names and len(sub_dict) > 0:
                    exit, sub_choices = self.choose_subtitle(sub_dict)
                    if exit:
                        break
                    for i, choice in enumerate(sub_choices):
                        sub_choice, link, session = choice
                        sub_dict.pop(sub_choice)
                        try:
                            if i == 0:
                                error, n_extract_sub_names = self.process_archive(
                                    one_video, video_info,
                                    sub_choice, link, session)
                            else:
                                error, n_extract_sub_names = self.process_archive(
                                    one_video, video_info,
                                    sub_choice, link, session,
                                    rename=False, delete=False)
                            if error:
                                print(prefix + ' error: ' + error)
                                print(prefix)
                                continue
                            elif not n_extract_sub_names:
                                print(prefix
                                      + ' no matched subtitle in this archive')
                                continue
                            else:
                                extract_sub_names += n_extract_sub_names
                        except TypeError as e:
                            print(format_exc())
                            continue
                        except (rarfile.BadRarFile, TypeError) as e:
                            print(prefix + ' Error:' + str(e))
                            continue
            except rarfile.RarCannotExec:
                self.s_error += 'Unrar not installed?'
            except AttributeError:
                self.s_error += 'unknown error. try again.'
                self.f_error += format_exc()
            except Exception as e:
                self.s_error += str(e) + '. '
                self.f_error += format_exc()
            finally:
                if ('extract_sub_names' in dir()
                        and not extract_sub_names
                        and len(sub_dict) == 0):
                    # 自动模式下所有字幕包均没有猜测字幕
                    self.s_error += " failed to guess one subtitle,"
                    self.s_error += "use '-q' to try query mode."

                if self.s_error and not self.debug:
                    self.s_error += "add --debug to get more info of the error"

                if self.s_error:
                    self.failed_list.append({'name': one_video,
                                             'path': video_info['path'],
                                             'error': self.s_error,
                                             'trace_back': self.f_error})
                    print(prefix + ' error:' + self.s_error)

        if len(self.failed_list):
            print('\n===============================', end='')
            print('FAILED LIST===============================\n')
            for i, one in enumerate(self.failed_list):
                print('%2s. name: %s' % (i + 1, one['name']))
                print('%3s path: %s' % ('', one['path']))
                print('%3s info: %s' % ('', one['error']))
                if self.debug:
                    print('%3s TRACE_BACK: %s' % ('', one['trace_back']))

        print('\ntotal: %s  success: %s  fail: %s\n' % (
            len(all_video_dict),
            len(all_video_dict) - len(self.failed_list),
            len(self.failed_list)
        ))

        return {
            'total': len(all_video_dict),
            'success': len(all_video_dict) - len(self.failed_list),
            'fail': len(self.failed_list),
            'fail_videos': self.failed_list
        }


def main():

    arg_parser = argparse.ArgumentParser(
        prog='GetSubtitles',
        epilog='getsub %s\n\n@guoyuhang' % (__version__),
        description='download subtitles easily',
        formatter_class=argparse.RawTextHelpFormatter
    )
    arg_parser.add_argument(
        'name',
        help="the video's name or full path or a dir with videos"
    )
    arg_parser.add_argument(
        '-p',
        '--directory',
        action='store',
        help='set specified subtitle download path'
    )
    arg_parser.add_argument(
        '-q',
        '--query',
        action='store_true',
        help='show search results and choose one to download'
    )
    arg_parser.add_argument(
        '-s',
        '--single',
        action='store_true',
        help='show subtitles in the compacted file and choose one to download'
    )
    arg_parser.add_argument(
        '-o',
        '--over',
        action='store_true',
        help='replace the subtitle already exists'
    )
    arg_parser.add_argument(
        '-m',
        '--more',
        action='store_true',
        help='save original download file.'
    )
    arg_parser.add_argument(
        '-n',
        '--number',
        action='store',
        help='set max number of subtitles to be choosen when in query mode'
    )
    arg_parser.add_argument(
        '-b',
        '--both',
        action='store_true',
        help='save .srt and .ass subtitles at the same time '
             'if two types exist in the same archive'
    )
    arg_parser.add_argument(
        '-d',
        '--downloader',
        action='store',
        help='choose downloader from ' +
        ', '.join(DownloaderManager.downloader_names)
    )
    arg_parser.add_argument(
        '--debug',
        action='store_true',
        help='show more info of the error'
    )
    arg_parser.add_argument(
        '--plex',
        action='store_true',
        help="add .zh to the subtitle's name for plex to recognize"
    )

    args = arg_parser.parse_args()

    if args.over:
        print('\nThe script will replace the old subtitles if exist...\n')

    GetSubtitles(args.name, args.query, args.single, args.more,
                 args.both, args.over, args.plex, args.debug, sub_num=args.number,
                 downloader=args.downloader, sub_path=args.directory,).start()


if __name__ == '__main__':
    main()
