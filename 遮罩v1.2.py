#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import random
import json
import requests
from bs4 import BeautifulSoup
import urllib.parse as urlparse
from urllib.robotparser import RobotFileParser
import warnings
import hashlib
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

warnings.filterwarnings("ignore")  # 忽略SSL警告

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='crawler.log',
    filemode='a'
)

# 全局爬取设置
CRAWL_SETTINGS = {
    'retry_times': 3,  # 重试次数
    'use_proxy': False,
    'proxy': None,     # 代理设置
    'ignore_ssl': False,  # 忽略SSL验证
    'dynamic_rendering': False,  # 动态渲染
    'request_delay': 0.5,  # 请求延迟(秒)
    'max_depth': 1,  # 链接挖掘深度
    'audio_sniffing': True,  # 音频嗅探
}


def get_random_ua():
    """获取随机User-Agent"""
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.48',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
    ]
    return random.choice(agents)
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
    except Exception as e:
        logging.warning(f"无法获取robots.txt: {str(e)}")
        return True  # 如果无法获取robots.txt，默认允许访问

def requests_retry_session():
    """创建带重试机制的session"""
    session = requests.Session()
    retry = Retry(
        total=CRAWL_SETTINGS['retry_times'],
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504, 429],
        allowed_methods=['GET', 'POST']
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def render_dynamic_page(url):
    """使用Selenium渲染动态页面（需要安装浏览器驱动）"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        logging.error("未安装Selenium，无法使用动态渲染")
        return None
    
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"user-agent={get_random_ua()}")
        
        # 设置代理
        if CRAWL_SETTINGS['use_proxy'] and CRAWL_SETTINGS['proxy']:
            proxy = CRAWL_SETTINGS['proxy']
            if proxy.startswith('socks'):
                options.add_argument(f'--proxy-server={proxy}')
            else:
                options.add_argument(f'--proxy-server={proxy}')
        
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        
        # 等待页面加载
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # 滚动页面以加载更多内容
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
        
        content = driver.page_source
        driver.quit()
        return content
    except Exception as e:
        logging.error(f"动态渲染失败: {str(e)}")
        return None

def find_audio_resources(soup, base_url):
    """查找页面中的音频资源"""
    audio_links = set()
    audio_extensions = ['.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac']
    
    # 查找<audio>标签
    for audio in soup.find_all('audio'):
        if audio.get('src'):
            audio_links.add(urlparse.urljoin(base_url, audio['src']))
        for source in audio.find_all('source'):
            if source.get('src'):
                audio_links.add(urlparse.urljoin(base_url, source['src']))
    
    # 查找带音频扩展名的链接
    for a in soup.find_all('a', href=True):
        href = a['href']
        if any(href.endswith(ext) for ext in audio_extensions):
            audio_links.add(urlparse.urljoin(base_url, href))
    
    # 查找JavaScript加载的音频资源
    for script in soup.find_all('script'):
        if script.string:
            for ext in audio_extensions:
                matches = re.findall(f'["\'](https?://.*?{ext})["\']', script.string, re.IGNORECASE)
                audio_links.update(urlparse.urljoin(base_url, m) for m in matches)
    
    return list(audio_links)

def extract_links(soup, base_url, max_depth):
    """提取页面中的所有链接"""
    links = set()
    parsed_base = urlparse.urlparse(base_url)
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        # 跳过锚点链接和空链接
        if not href or href.startswith('#'):
            continue
        
        # 处理相对链接
        full_url = urlparse.urljoin(base_url, href)
        parsed = urlparse.urlparse(full_url)
        
        # 只保留同源链接
        if parsed.netloc == parsed_base.netloc:
            links.add(full_url)
    
    # 限制链接数量
    return list(links)[:10 * max_depth]  # 每层最多10个链接

def fetch_web_content(url):
    """获取网页内容并提取所有文本（高级破限）"""
    # 随机延迟防止被封
    time.sleep(random.uniform(CRAWL_SETTINGS['request_delay'], CRAWL_SETTINGS['request_delay'] * 2))
    
    session = requests_retry_session()
    headers = {
        'User-Agent': get_random_ua(),
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Referer': 'https://www.google.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }
    
    proxies = None
    if CRAWL_SETTINGS['use_proxy'] and CRAWL_SETTINGS['proxy']:
        proxies = {
            'http': CRAWL_SETTINGS['proxy'],
            'https': CRAWL_SETTINGS['proxy'],
        }
    
    verify = not CRAWL_SETTINGS['ignore_ssl']
    content = None
    audio_resources = []
    
    try:
        # 动态渲染处理
        if CRAWL_SETTINGS['dynamic_rendering']:
            content = render_dynamic_page(url)
        
        # 如果动态渲染失败或未启用，使用requests
        if not content:
            response = session.get(
                url, 
                headers=headers, 
                timeout=15, 
                proxies=proxies,
                verify=verify
            )
            response.encoding = response.apparent_encoding
            content = response.text
            
            if response.status_code != 200:
                return None, [], f"错误: HTTP状态码 {response.status_code}"
        
        # 解析内容
        try:
            soup = BeautifulSoup(content, 'lxml')
        except Exception:
            try:
                soup = BeautifulSoup(content, 'html.parser')
            except Exception as e:
                return None, [], f"解析失败: {str(e)}"
        
        # 音频嗅探
        if CRAWL_SETTINGS['audio_sniffing']:
            audio_resources = find_audio_resources(soup, url)
            logging.info(f"找到 {len(audio_resources)} 个音频资源")
        
        # 移除不需要的元素
        for element in soup(['script', 'style', 'noscript', 'meta', 'link', 'header', 'footer', 'nav', 'aside', 'form', 'iframe']):
            element.decompose()
        
        # 提取所有文本
        text = ""
        # 优先提取主要内容区域
        main_content = soup.find(['main', 'article']) or soup.find(class_=re.compile(r'content|main|post|article'))
        if main_content:
            for element in main_content.find_all(['p', 'div', 'section']):
                if element.get_text(strip=True):
                    text += element.get_text(strip=False) + '\n\n'
        else:
            # 备用方法：提取所有文本
            for element in soup.find_all(['p', 'div', 'article', 'section']):
                if element.get_text(strip=True) and len(element.get_text(strip=True)) > 30:
                    text += element.get_text(strip=False) + '\n\n'
        
        # 如果没有提取到内容，使用最后手段
        if not text.strip():
            text = soup.get_text()
        
        # 清理文本
        cleaned_text = re.sub(r'\n{3,}', '\n\n', text)  # 减少过多换行
        cleaned_text = re.sub(r'[ \t]{2,}', ' ', cleaned_text)  # 减少过多空格
        cleaned_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b]', '', cleaned_text)  # 移除控制字符
        
        return cleaned_text, audio_resources, None
    
    except Exception as e:
        logging.error(f"抓取失败: {str(e)}")
        return None, [], f"抓取失败: {str(e)}"

def download_audio(url, base_url):
    """下载音频文件"""
    try:
        parsed = urlparse.urlparse(url)
        filename = os.path.basename(parsed.path) or f"audio_{hashlib.md5(url.encode()).hexdigest()[:8]}.mp3"
        
        # 创建音频目录
        domain = urlparse.urlparse(base_url).netloc.replace('www.', '')
        audio_dir = f"{domain}_audio"
        os.makedirs(audio_dir, exist_ok=True)
        filepath = os.path.join(audio_dir, filename)
        
        headers = {
            'User-Agent': get_random_ua(),
            'Referer': base_url,
        }
        
        proxies = None
        if CRAWL_SETTINGS['use_proxy'] and CRAWL_SETTINGS['proxy']:
            proxies = {
                'http': CRAWL_SETTINGS['proxy'],
                'https': CRAWL_SETTINGS['proxy'],
            }
        
        response = requests.get(
            url, 
            headers=headers, 
            timeout=15, 
            proxies=proxies,
            stream=True
        )
        
        if response.status_code != 200:
            return None, f"下载失败: HTTP {response.status_code}"
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return filepath, None
    
    except Exception as e:
        logging.error(f"音频下载失败: {str(e)}")
        return None, f"音频下载失败: {str(e)}"

def save_to_file(content, base_url, file_type="text"):
    """保存内容到文件"""
    domain = urlparse.urlparse(base_url).netloc.replace('www.', '')
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    if file_type == "text":
        filename = f"{domain}_{timestamp}.txt"
        content_to_save = content
    elif file_type == "links":
        filename = f"{domain}_links_{timestamp}.txt"
        content_to_save = "\n".join(content)
    elif file_type == "audio_list":
        filename = f"{domain}_audio_links_{timestamp}.txt"
        content_to_save = "\n".join(content)
    else:
        return None, "无效的文件类型"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content_to_save)
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
        print(f"4. 动态渲染: {'是' if CRAWL_SETTINGS['dynamic_rendering'] else '否'} (需要安装Selenium)")
        print(f"5. 请求延迟: {CRAWL_SETTINGS['request_delay']}秒")
        print(f"6. 链接挖掘深度: {CRAWL_SETTINGS['max_depth']}层")
        print(f"7. 音频嗅探: {'启用' if CRAWL_SETTINGS['audio_sniffing'] else '禁用'}")
        print("\n8. 保存当前配置")
        print("9. 加载配置")
        print("10. 返回主菜单")
        
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
            
        elif choice == '4':
            print("\n是否启用动态渲染（需要安装Selenium）？(y/n):")
            dynamic = input("> ").lower()
            CRAWL_SETTINGS['dynamic_rendering'] = (dynamic == 'y')
            if dynamic == 'y':
                print("警告：动态渲染需要安装Selenium和浏览器驱动")
            print(f"动态渲染已{'启用' if dynamic=='y' else '禁用'}！")
            input("\n按Enter继续...")
            
        elif choice == '5':
            print("\n请输入请求延迟时间（秒，0-5）:")
            delay = input("> ")
            try:
                delay = float(delay)
                if 0 <= delay <= 5:
                    CRAWL_SETTINGS['request_delay'] = delay
                    print("设置成功！")
                else:
                    print("输入超出范围")
            except:
                print("输入无效")
            input("\n按Enter继续...")
            
        elif choice == '6':
            print("\n请输入链接挖掘深度（0-3）:")
            depth = input("> ")
            if depth.isdigit() and 0 <= int(depth) <= 3:
                CRAWL_SETTINGS['max_depth'] = int(depth)
                print("设置成功！")
            else:
                print("输入无效，请输入0-3之间的整数。")
            input("\n按Enter继续...")
            
        elif choice == '7':
            print("\n是否启用音频嗅探？(y/n):")
            audio = input("> ").lower()
            CRAWL_SETTINGS['audio_sniffing'] = (audio == 'y')
            print(f"音频嗅探已{'启用' if audio=='y' else '禁用'}！")
            input("\n按Enter继续...")
            
        elif choice == '8':
            try:
                with open('crawler_config.json', 'w') as f:
                    json.dump(CRAWL_SETTINGS, f)
                print("配置已保存到 crawler_config.json")
            except Exception as e:
                print(f"保存配置失败: {str(e)}")
            input("\n按Enter继续...")
            
        elif choice == '9':
            try:
                with open('crawler_config.json', 'r') as f:
                    CRAWL_SETTINGS = json.load(f)
                print("配置已加载")
            except FileNotFoundError:
                print("配置文件不存在")
            except Exception as e:
                print(f"加载配置失败: {str(e)}")
            input("\n按Enter继续...")
            
        elif choice == '10' or choice == 'q':
            break
            
        else:
            print("无效输入！")
            input("\n按Enter继续...")

def main():
    clear_screen()
    print("""
███████╗██████╗ ███████╗ ██████╗ █████╗ ███████╗
██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗██╔════╝
█████╗  ██████╔╝███████╗██║     ███████║███████╗
██╔══╝  ██╔══██╗╚════██║██║     ██╔══██║╚════██║
███████╗██║  ██║███████║╚██████╗██║  ██║███████║
╚══════╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚══════╝
超级网页爬虫 v2.0 · 支持音频嗅探和破限技术
==============================================""")
    
    # 尝试加载配置
    try:
        with open('crawler_config.json', 'r') as f:
            CRAWL_SETTINGS.update(json.load(f))
    except:
        pass
    
    current_url = None
    web_content = None
    audio_resources = []
    found_links = []

    while True:
        clear_screen()
        print(f"\n当前状态: {f'已加载 {urlparse.urlparse(current_url).netloc}' if current_url else '未加载网页'}")
        if audio_resources:
            print(f"已发现音频资源: {len(audio_resources)}个")
        if found_links:
            print(f"已发现链接: {len(found_links)}个")
        print("==============================================")
        
        main_menu = [
            "输入网址抓取内容",
            "预览抓取的文本",
            "保存文本到文件",
            "嗅探并下载音频",
            "高级设置",
            "清除当前数据"
        ]
        
        display_menu(main_menu, "主菜单")
        choice = input("\n>>> ").strip().lower()
        
        if choice == 'q':
            print("\n感谢使用超级爬虫！")
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
                
                content, audio_links, error = fetch_web_content(current_url)
                if error:
                    print(f"抓取失败: {error}")
                    current_url = None
                else:
                    web_content = content
                    audio_resources = audio_links
                    
                    # 链接挖掘
                    if CRAWL_SETTINGS['max_depth'] > 0:
                        print("\n正在挖掘页面链接...")
                        try:
                            response = requests.get(current_url, timeout=10)
                            soup = BeautifulSoup(response.text, 'lxml')
                            found_links = extract_links(soup, current_url, CRAWL_SETTINGS['max_depth'])
                            print(f"发现 {len(found_links)} 个链接")
                        except:
                            print("链接挖掘失败")
                    
                    print(f"\n抓取成功！文本长度: {len(web_content)}字符")
                    if audio_resources:
                        print(f"发现 {len(audio_resources)} 个音频资源")
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
                
                if found_links:
                    print(f"\n{' 发现链接 ':-^50}")
                    for i, link in enumerate(found_links[:5], 1):
                        print(f"{i}. {link[:80]}{'...' if len(link) > 80 else ''}")
                    if len(found_links) > 5:
                        print(f"...显示前5/{len(found_links)}个链接")
                
                input("\n按Enter返回主菜单...")
                
        elif choice == '3':
            if not web_content and not found_links:
                print("\n没有可保存的内容！")
                input("按Enter继续...")
            else:
                file_type = None
                content_to_save = None
                
                if web_content:
                    file_type = "text"
                    content_to_save = web_content
                elif found_links:
                    file_type = "links"
                    content_to_save = found_links
                
                filename, error = save_to_file(content_to_save, current_url, file_type)
                if error:
                    print(error)
                else:
                    abs_path = os.path.abspath(filename)
                    print(f"保存成功！文件位置: {abs_path}")
                input("\n按Enter返回主菜单...")
                
        elif choice == '4':
            if not audio_resources:
                print("\n没有可下载的音频资源！")
                input("按Enter继续...")
            else:
                clear_screen()
                print(f"\n{' 音频资源列表 ':=^50}")
                for i, audio_url in enumerate(audio_resources, 1):
                    print(f"{i}. {audio_url[:80]}{'...' if len(audio_url) > 80 else ''}")
                print(f"共发现 {len(audio_resources)} 个音频资源")
                print("\n输入要下载的音频编号（1-N）")
                print("输入 a 下载全部音频")
                print("输入 s 保存音频链接到文件")
                print("输入 b 返回主菜单")
                
                while True:
                    choice = input("\n>>> ").strip().lower()
                    
                    if choice == 'b':
                        break
                        
                    elif choice == 'a':
                        print(f"开始下载所有 {len(audio_resources)} 个音频资源...")
                        success = 0
                        errors = []
                        
                        for i, audio_url in enumerate(audio_resources, 1):
                            print(f"\n下载中 [{i}/{len(audio_resources)}]: {audio_url[:60]}...")
                            filepath, error = download_audio(audio_url, current_url)
                            if error:
                                print(f"下载失败: {error}")
                                errors.append(f"音频 {i}: {error}")
                            else:
                                print(f"下载成功: {filepath}")
                                success += 1
                        
                        print(f"\n下载完成! 成功: {success}, 失败: {len(errors)}")
                        if errors:
                            print("错误列表:")
                            for e in errors:
                                print(f" - {e}")
                        
                        input("\n按Enter返回音频菜单...")
                        break
                        
                    elif choice == 's':
                        filename, error = save_to_file(audio_resources, current_url, "audio_list")
                        if error:
                            print(error)
                        else:
                            abs_path = os.path.abspath(filename)
                            print(f"音频链接已保存到: {abs_path}")
                        input("\n按Enter返回音频菜单...")
                        break
                    
                    elif choice.isdigit():
                        index = int(choice) - 1
                        if 0 <= index < len(audio_resources):
                            audio_url = audio_resources[index]
                            print(f"\n开始下载: {audio_url}")
                            filepath, error = download_audio(audio_url, current_url)
                            if error:
                                print(f"下载失败: {error}")
                            else:
                                print(f"下载成功: {filepath}")
                        else:
                            print("无效的音频编号!")
                        input("\n按Enter返回音频菜单...")
                        break
                    
                    else:
                        print("无效输入! 请重新选择")
                
        elif choice == '5':
            advanced_settings()
            
        elif choice == '6':
            current_url = None
            web_content = None
            audio_resources = []
            found_links = []
            print("\n数据已重置!")
            input("按Enter继续...")
            
        else:
            print("\n无效输入！请选择1-6")
            input("按Enter继续...")

if __name__ == "__main__":
    main()
