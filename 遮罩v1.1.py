#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup
import urllib.parse as urlparse
from urllib.robotparser import RobotFileParser
import warnings
warnings.filterwarnings("ignore")  # 忽略SSL警告

# 随机User-Agent列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.48',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
]

# 全局爬取设置
CRAWL_SETTINGS = {
    'retry_times': 3,  # 重试次数
    'use_proxy': False,
    'proxy': None,     # 代理设置
    'ignore_ssl': False,  # 忽略SSL验证
}

def clear_screen():
    """清空命令行屏幕"""
    os.system('cls' if os.name == 'nt' else 'clear')

def validate_url(url):
    """验证URL格式有效性"""
    parsed = urlparse.urlparse(url)
    if not parsed.scheme:
        url = 'http://' + url
    return url if re.match(r'^https?://', url) else None

def get_robots_permission(url):
    """检查robots.txt权限"""
    parsed = urlparse.urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    rp = RobotFileParser()
    rp.set_url(urlparse.urljoin(base_url, "/robots.txt"))
    try:
        rp.read()
        return rp.can_fetch("*", url)
    except:
        return True  # 如果无法获取robots.txt，默认允许访问

def fetch_web_content(url):
    """获取网页内容并提取所有文本（支持重试、随机UA、代理、忽略SSL）"""
    retry = CRAWL_SETTINGS['retry_times']
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    proxies = None
    if CRAWL_SETTINGS['use_proxy'] and CRAWL_SETTINGS['proxy']:
        proxies = {
            'http': CRAWL_SETTINGS['proxy'],
            'https': CRAWL_SETTINGS['proxy'],
        }
    
    verify = not CRAWL_SETTINGS['ignore_ssl']
    
    for attempt in range(retry + 1):
        try:
            response = requests.get(
                url, 
                headers=headers, 
                timeout=10, 
                proxies=proxies,
                verify=verify
            )
            response.encoding = response.apparent_encoding
            
            if response.status_code != 200:
                return None, f"错误: HTTP状态码 {response.status_code}"
            
            # ==== 修复关键部分 ====
            try:
                soup = BeautifulSoup(response.text, 'lxml')
            except Exception:
                try:
                    soup = BeautifulSoup(response.text, 'html.parser')
                except Exception as e:
                    return None, f"解析失败: {str(e)}"
            # ====================
            
            # 移除不需要的元素
            for element in soup(['script', 'style', 'noscript', 'meta', 'link', 'header', 'footer', 'nav', 'aside', 'form']):
                element.decompose()
            
            # 提取所有文本并保留段落结构
            text = ""
            for element in soup.find_all(['p', 'div', 'article', 'section']):
                if element.name == 'p' or (element.get_text(strip=True) and len(element.get_text(strip=True)) > 30):
                    text += element.get_text(strip=False) + '\n\n'
            
            # 如果没有提取到内容，使用备用方法
            if not text.strip():
                text = soup.get_text()
            
            # 清理文本
            cleaned_text = re.sub(r'\n{3,}', '\n\n', text)  # 减少过多换行
            cleaned_text = re.sub(r'[ \t]{2,}', ' ', cleaned_text)  # 减少过多空格
            cleaned_text = re.sub(r'\u200b', '', cleaned_text)  # 移除零宽空格
            
            return cleaned_text, None
        
        except Exception as e:
            if attempt == retry:
                return None, f"抓取失败: {str(e)}"
            time.sleep(1)  # 延迟1秒重试

def save_to_file(content, base_url):
    """保存文本到文件"""
    domain = urlparse.urlparse(base_url).netloc.replace('www.', '')
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{domain}_{timestamp}.txt"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        return filename, None
    except Exception as e:
        return None, f"保存失败: {str(e)}"

def display_menu(options, title=None):
    """显示命令行菜单"""
    if title:
        print(f"\n{' '*(len(title)+4)}")
        print(f"  {title}  ")
        print(f"{' '*(len(title)+4)}\n")
    
    for i, option in enumerate(options, 1):
        print(f"{i}. {option}")
    print("\n输入数字选择，输入q退出")

def advanced_settings():
    """高级设置菜单"""
    global CRAWL_SETTINGS
    while True:
        clear_screen()
        print("\n高级设置")
        print("========")
        print(f"1. 重试次数: {CRAWL_SETTINGS['retry_times']}")
        print(f"2. 使用代理: {'是' if CRAWL_SETTINGS['use_proxy'] else '否'} [当前代理: {CRAWL_SETTINGS['proxy']}]")
        print(f"3. 忽略SSL验证: {'是' if CRAWL_SETTINGS['ignore_ssl'] else '否'}")
        print("\n4. 返回主菜单")
        
        choice = input("\n>>> ").strip().lower()
        
        if choice == '1':
            print("\n请输入重试次数（0-5）:")
            retry = input("> ")
            if retry.isdigit() and 0 <= int(retry) <= 5:
                CRAWL_SETTINGS['retry_times'] = int(retry)
                print("设置成功！")
            else:
                print("输入无效，请输入0-5之间的整数。")
            input("\n按Enter继续...")
            
        elif choice == '2':
            print("\n是否使用代理？(y/n):")
            use_proxy = input("> ").lower()
            if use_proxy == 'y':
                CRAWL_SETTINGS['use_proxy'] = True
                print("请输入代理地址（例如：http://127.0.0.1:1080）:")
                proxy = input("> ").strip()
                if proxy:
                    CRAWL_SETTINGS['proxy'] = proxy
                    print("代理设置成功！")
                else:
                    print("代理地址不能为空，已取消。")
            else:
                CRAWL_SETTINGS['use_proxy'] = False
                print("已关闭代理。")
            input("\n按Enter继续...")
            
        elif choice == '3':
            print("\n是否忽略SSL验证（可能不安全）？(y/n):")
            ignore_ssl = input("> ").lower()
            CRAWL_SETTINGS['ignore_ssl'] = (ignore_ssl == 'y')
            print(f"忽略SSL验证已{'启用' if ignore_ssl=='y' else '禁用'}！")
            input("\n按Enter继续...")
            
        elif choice == '4' or choice == 'q':
            break
            
        else:
            print("无效输入！")

def main():
    clear_screen()
    print("""
███████╗██████╗ ███████╗ ██████╗ █████╗ ███████╗
██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗██╔════╝
█████╗  ██████╔╝███████╗██║     ███████║███████╗
██╔══╝  ██╔══██╗╚════██║██║     ██╔══██║╚════██║
███████╗██║  ██║███████║╚██████╗██║  ██║███████║
╚══════╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚══════╝
命令行网页爬虫 v1.5 · 输入数字进行操作
==============================================""")
    
    current_url = None
    web_content = None

    while True:
        clear_screen()
        print(f"\n当前状态: {f'已加载 {urlparse.urlparse(current_url).netloc}' if current_url else '未加载网页'}")
        print("==============================================")
        
        main_menu = [
            "输入网址抓取内容",
            "预览抓取的文本",
            "保存到文件",
            "高级设置",
            "清除当前数据"
        ]
        
        display_menu(main_menu, "主菜单")
        choice = input("\n>>> ").strip().lower()
        
        if choice == 'q':
            print("\n感谢使用遮罩爬虫！")
            break
            
        elif choice == '1':
            while True:
                print("\n请输入要抓取的完整网址（例如：https://example.com）")
                print("输入b返回主菜单")
                url_input = input("\nURL> ").strip()
                
                if url_input.lower() == 'b':
                    break
                    
                valid_url = validate_url(url_input)
                if not valid_url:
                    print("无效的URL！请包含http://或https://")
                    continue
                
                # 检查robots.txt权限
                if not get_robots_permission(valid_url):
                    print("警告：该网站禁止爬虫抓取！继续操作可能违反服务条款。")
                    proceed = input("仍要继续吗？(y/N): ").lower()
                    if proceed != 'y':
                        continue
                
                current_url = valid_url
                print(f"正在抓取: {current_url}")
                
                content, error = fetch_web_content(current_url)
                if error:
                    print(f"抓取失败: {error}")
                    current_url = None
                else:
                    web_content = content
                    print(f"抓取成功！文本长度: {len(web_content)}字符")
                    input("\n按Enter返回主菜单...")
                    break
                    
        elif choice == '2':
            if not web_content:
                print("\n请先抓取网页内容！")
                input("按Enter继续...")
            else:
                clear_screen()
                print(f"\n{' 文本预览 ':-^50}")
                print(web_content[:1000] + ("" if len(web_content) <= 1000 else "..."))
                print(f"{' END ':-^50}")
                print(f"总长度: {len(web_content)}字符 | 显示前1000字符")
                input("\n按Enter返回主菜单...")
                
        elif choice == '3':
            if not web_content:
                print("\n没有可保存的内容！")
                input("按Enter继续...")
            else:
                filename, error = save_to_file(web_content, current_url)
                if error:
                    print(error)
                else:
                    abs_path = os.path.abspath(filename)
                    print(f"保存成功！文件位置: {abs_path}")
                input("\n按Enter返回主菜单...")
                
        elif choice == '4':
            advanced_settings()
            
        elif choice == '5':
            current_url = None
            web_content = None
            print("\n数据已重置!")
            input("按Enter继续...")
            
        else:
            print("\n无效输入！请选择1-5")
            input("按Enter继续...")

if __name__ == "__main__":
    main()
