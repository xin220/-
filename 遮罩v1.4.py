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
import threading
import concurrent.futures
import shutil
import html
import chardet

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
    'image_crawling': True,  # 图片爬取
    'max_threads': 5,  # 最大下载线程数
    'image_size_limit': 10,  # 图片大小限制(MB)
    'text_crawling': True,   # 新增：文本爬取开关
}

# 增强版User-Agent列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows极速加速器 NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.极速加速器1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Whale/3.24.223.18 Safari/537.36'
]

def get_random_ua():
    """获取随机User-Agent"""
    return random.choice(USER_AGENTS)

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
            proxy = C极速加速器RAWL_SETTINGS['proxy']
            if proxy.startswith('socks'):
                options.add_argument(f'--proxy-server={proxy}')
            else:
                options.add_argument(f'--proxy-server={proxy}')
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)  # 设置超时时间
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

def find_image_resources(soup, base_url):
    """查找页面中的所有图片资源"""
    image_links = set()
    
    # 查找标签
    for img in soup.find_all('img', src=True):
        src = img['src'].strip()
        if src:
            # 处理相对URL
            image_links.add(urlparse.urljoin(base_url, src))
    
    # 查找CSS背景图片
    for element in soup.find_all(style=True):
        style = element['style']
        # 使用正则表达式匹配背景图片URL
        matches = re.findall(r'url\(["\']?(.*?)["\']?\)', style, re.IGNORECASE)
        for url in matches:
            if url.startswith('data:'):
                continue  # 跳过内联图片
            image_links.add(urlparse.urljoin(base_url, url))
    
    # 查找JavaScript加载的图片资源
    for script in soup.find_all('script'):
        if script.string:
            # 匹配图片URL模式
            matches = re.findall(r'["\'](https?://.*?\.(?:jpg|jpeg|png|gif|webp|bmp))["\']', script.string, re.IGNORECASE)
            for url in matches:
                image_links.add(urlparse.urljoin(base_url, url))
    
    return list(image_links)

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
    """获取网页内容并提取所有文本（增强版破限）"""
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
        'Pragma': 'no-cache',
    }
    
    proxies = None
    if CRAWL_SETTINGS['use_proxy'] and CRAWL_SETTINGS['proxy']:
        proxies = {
            'http': CRAWL_SETTINGS['proxy'],
            'https': CRAWL_SETTINGS['proxy'],
        }
    
    verify = not CRAWL_SETTINGS['ignore_ssl']
    content = None
    image_resources = []
    
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
            
            # 增强的编码检测
            if not response.encoding or response.encoding.lower() == 'iso-8859-1':
                # 使用chardet检测编码
                encoding_detected = chardet.detect(response.content)['encoding']
                if encoding_detected:
                    response.encoding = encoding_detected
            
            # 处理乱码问题
            try:
                content = response.text
            except UnicodeDecodeError:
                content = response.content.decode('utf-8', errors='replace')
            
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
        
        # 图片爬取
        if CRAWL_SETTINGS['image_crawling']:
            image_resources = find_image_resources(soup, url)
            logging.info(f"找到 {len(image_resources)} 张图片")
        
        # 文本爬取（新增独立的文本爬取功能）
        text = ""
        if CRAWL_SETTINGS['text_crawling']:
            # 增强的破限技术
            # 尝试多种方法提取主要内容
            
            # 方法1: 查找article/main标签
            main_content = soup.find(['article', 'main'])
            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            
            # 方法2: 查找内容类名
            if not text:
                for class_name in ['content', 'article', 'main-content', 'post-content']:
                    content_div = soup.find(class_=class_name)
                    if content_div:
                        text = content_div.get_text(separator='\n', strip=True)
                        if text:
                            break
            
            # 方法3: 使用启发式算法（段落密度）
            if not text:
                paragraphs = soup.find_all(['p', 'div'])
                text_candidates = []
                
                for p in paragraphs:
                    # 跳过小段落
                    if len(p.get_text(strip=True)) < 50:
                        continue
                    
                    # 计算链接密度
                    links = p.find_all('a')
                    link_text_length = sum(len(a.get_text(strip=True)) for a in links)
                    total_text_length = len(p.get_text(strip=True))
                    link_density = link_text_length / total_text_length if total_text_length > 0 else 0
                    
                    # 跳过高链接密度段落（广告/导航）
                    if link_density < 0.3:
                        text_candidates.append(p.get_text(strip=True))
                
                if text_candidates:
                    text = '\n\n'.join(text_candidates)
            
            # 方法4: 作为最后手段，提取所有文本
            if not text:
                text = soup.get_text(separator='\n', strip=True)
            
            # 清理和格式化文本
            # 1. 合并多余的空行
            cleaned_text = re.sub(r'\n{3,}', '\n\n', text)
            # 2. 删除HTML实体
            cleaned_text = html.unescape(cleaned_text)
            # 3. 删除特殊字符
            cleaned_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b]', '', cleaned_text)
            # 4. 删除首尾空白
            cleaned_text = cleaned_text.strip()
        else:
            cleaned_text = ""
        
        return cleaned_text, image_resources, None
    
    except Exception as e:
        logging.error(f"抓取失败: {str(e)}")
        return None, [], f"抓取失败: {str(e)}"

def download_image(url, base_url, index=None, total=None):
    """下载图片文件"""
    try:
        parsed = urlparse.urlparse(url)
        filename = os.path.basename(parsed.path) or f"image_{hashlib.md5(url.encode()).hexdigest()[:8]}.jpg"
        
        # 创建图片目录
        domain = urlparse.urlparse(base_url).netloc.replace('www.', '')
        image_dir = f"{domain}_images"
        os.makedirs(image_dir, exist_ok=True)
        filepath = os.path.join(image_dir, filename)
        
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
        
        # 仅获取文件大小信息
        head_response = requests.head(
            url, 
            headers=headers, 
            timeout=10, 
            proxies=proxies,
            allow_redirects=True
        )
        
        # 检查文件大小
        if 'Content-Length' in head_response.headers:
            file_size = int(head_response.headers['Content-Length']) / (1024 * 1024)  # 转换为MB
            if file_size > CRAWL_SETTINGS['image_size_limit']:
                return None, f"图片过大({file_size:.2f}MB > {CRAWL_SETTINGS['image_size_limit']}MB)，跳过下载"
        
        # 下载图片
        with requests.get(
            url, 
            headers=headers, 
            timeout=30, 
            proxies=proxies,
            stream=True
        ) as response:
            if response.status_code != 200:
                return None, f"下载失败: HTTP {response.status_code}"
            
            # 保存图片
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        # 返回带进度信息的成功消息
        if index is not None and total is not None:
            return filepath, f"成功 [{index}/{total}]"
        return filepath, None
    
    except Exception as e:
        logging.error(f"图片下载失败: {str(e)}")
        return None, f"图片下载失败: {str(e)}"

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
    elif file_type == "image_list":
        filename = f"{domain}_image_links_{timestamp}.txt"
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
        print(f"7. 图片爬取: {'启用' if CRAWL_SETTINGS['image_crawling'] else '禁用'}")
        print(f"8. 最大下载线程极速加速器数: {CRAWL_SETTINGS['max_threads']}")
        print(f"9. 图片大小限制: {CRAWL_SETTINGS['image_size_limit']}MB")
        print(f"10. 文本爬取: {'启用' if CRAWL_SETTINGS['text_c极速加速器rawling'] else '禁用'}")  # 新增文本爬取开关
        print("\n11. 保存当前配置")
        print("12. 加载配置")
        print("13. 返回主菜单")
        
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
            print("\n是否启用动态渲染（需要安装Selenium）？(极速加速器y/n):")
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
            print("\n是否启用图片爬取？(y/n):")
            image = input("> ").lower()
            CRAWL_SETTINGS['image_crawling'] = (image == 'y')
            print(f"图片爬取已{'启用' if image=='y' else '禁用'}！")
            input("\n按Enter继续...")
            
        elif choice == '8':
            print("\n请输入最大下载线程数（1-20）:")
            threads = input("> ")
            if threads.isdigit() and 1 <= int(threads) <= 20:
                CRAWL_SETTINGS['max_threads'] = int(threads)
                print("设置成功！")
            else:
                print("输入无效，请输入1-20之间的整数。")
            input("\n按Enter继续...")
            
        elif choice == '9':
            print("\n请输入图片大小限制（MB，1-100）:")
            size = input("> ")
            if size.isdigit() and 1 <= int(size) <= 100:
                CRAWL_SETTINGS['image_size_limit'] = int(size)
                print("设置成功！")
            else:
                print("输入无效，请输入1-100之间的整数。")
            input("\n按Enter继续...")
            
        elif choice == '10':  # 新增文本爬取开关
            print("\n是否启用文本爬取？(y/n):")
            text = input("> ").lower()
            CRAWL_SETTINGS['text_crawling'] = (text == 'y')
            print(f"文本爬取已{'启用' if text=='y' else '禁用'}！")
            input("\n按Enter继续...")
            
        elif choice == '11':
            try:
                with open('crawler_config.json', 'w') as f:
                    json.dump(CRAWL_SETTINGS, f)
                print("配置已保存到 crawler_config.json")
            except Exception as e:
                print(f"保存配置失败: {str(e)}")
            input("\n按Enter继续...")
            
        elif choice == '12':
            try:
                with open('crawler_config.json', 'r') as f:
                    CRAWL_SETTINGS = json.load(f)
                print("配置已加载")
            except FileNotFoundError:
                print("配置文件不存在")
            except Exception as e:
                print(f"加载配置失败: {str(e)}")
            input("\n按Enter继续...")
            
        elif choice == '13' or choice == 'q':
            break
            
        else:
            print("无效输入！")
            input("\n按Enter继续...")
            
def main():
    clear_screen()
    print("""
███████╗╗╗╗╗╗╗╗██████╗╗╗╗╗╗╗╗ ██████████╗╗╗╗╗╗╗╗ █████████╗╗╗╗╗╗╗╗ ████████╗╗╗╗╗╗╗╗ ██████████╗╗╗╗╗╗╗╗
██╔╔╔╔╔╔╔╔════╝╝╝╝╝╝╝╝██╔╔╔╔╔╔╔╔══██╗╗╗╗╗╗╗╗██╔╔╔╔╔╔╔╔════╝╝╝╝╝╝╝╝██╔╔╔╔╔╔╔╔════╝╝╝╝╝╝╝╝██╔╔╔╔╔╔╔╔══██╗╗╗╗╗╗╗╗██╔╔╔╔╔╔╔╔════╝╝╝╝╝╝╝╝
█████╗╗╗╗╗╗╗╗  █████████╔╔╔╔╔╔╔╔╝╝╝╝╝╝╝╝███████╗╗╗╗╗╗╗╗██║║║║║║║║     ██████████║║║║║║║║███████╗╗╗╗╗╗╗╗
██╔╔╔╔╔╔╔╔══╝╝╝╝╝╝╝╝  █████╔╔╔╔╔╔╔╔══██╗╗╗╗╗╗╗╗╚╚╚╚╚╚╚╚════██║║║║║║║║██║║║║║║║║     █████╔╔╔╔╔╔╔╔══██║║║║║║║║╚╚╚╚╚╚╚╚════██║║极速加速器║║║║║
███████╗╗╗╗╗╗╗╗██║║║║║║║║  █████║║║║║║║║███████║║║║║║║║╚╚╚╚╚╚╚╚██████╗╗╗╗╗╗╗╗██║║║║║║║║  █████║║║║║║║║███████║║║║║║║║
╚╚╚╚╚╚╚╚══════╝╝╝╝╝╝╝╝╚╚╚╚╚╚╚╚═╝╝╝╝╝╝╝╝  ╚╚╚╚╚╚╚╚╚╚╚╚╚╚╚═╝╝╝╝╝╝╝╝╚╚╚╚╚╚╚╚══════╝╝╝╝╝╝╝╝ ╚╚╚╚╚╚╚╚╚╚╚╚╚╚╚═════╝╝╝╝╝╝╝╝╚╚╚╚╚╚╚╚═╝╝╝╝╝╝╝╝  ╚╚╚╚╚╚╚╚╚╚╚╚╚╚╚═╝╝╝╝╝╝╝╝╚╚╚╚╚╚╚╚══════╝╝╝╝╝╝╝╝
超级网页爬虫 v4.0 · 分离式文本/图片爬取 · 增强破限技术
==============================================""")
    
    # 尝试加载配置
    try:
        with open('crawler_config.json', 'r') as f:
            CRAWL_SETTINGS.update(json.load(f))
    except:
        pass
    
    current_url = None
    web_content = None
    image_resources = []
    found_links = []

    while True:
        try:
            clear_screen()
            print(f"\n当前状态: {f'已加载 {urlparse.urlparse(current_url).netloc}' if current_url else '未加载网页'}")
            if web_content:
                print(f"已爬取文本: {len(web_content)}字符")
            if image_resources:
                print(f"已发现图片资源: {len(image_resources)}张")
            if found_links:
                print(f"已发现链接: {len(found_links)}个")
            print("==============================================")
            
            main_menu = [
                "输入网址抓取内容",
                "预览抓取的文本",
                "保存文本到文件",
                "下载图片资源",
                "高级设置",
                "清除当前数据"
            ]
            
            display_menu(main_menu, "主菜单")
            choice = input("\n>>> ").strip().lower()
            
            if choice == 'q':
                print("\n感谢使用超级爬虫！")
                break
                
            elif choice == '1':  # 输入网址抓取内容
                while True:
                    print("\n[网页抓取模式]")
                    print("请输入要抓取的完整网址（例如：https://example.com）")
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
                    
                    # 调用增强版抓取函数
                    content, images, error = fetch_web_content(current_url)
                    if error:
                        print(f"抓取失败: {error}")
                        current_url = None
                    else:
                        web_content = content
                        image_resources = images
                        
                        # 链接挖掘
                        if CRAWL_SETTINGS['max_depth'] > 0:
                            print("\n正在挖掘页面链接...")
                            try:
                                # 获取页面内容用于链接挖掘
                                if not content:
                                    session = requests_retry_session()
                                    headers = {'User-Agent': get_random_ua()}
                                    proxies = None
                                    if CRAWL_SETTINGS['use_proxy'] and CRAWL_SETTINGS['proxy']:
                                        proxies = {
                                            'http': CRAWL_SETTINGS['proxy'],
                                            'https': CRAWL_SETTINGS['proxy'],
                                        }
                                    response = session.get(
                                        current_url, 
                                        headers=headers, 
                                        proxies=proxies,
                                        verify=not CRAWL_SETTINGS['ignore_ssl']
                                    )
                                    content = response.text
                                
                                soup = BeautifulSoup(content, 'lxml')
                                found_links = extract_links(soup, current_url, CRAWL_SETTINGS['max_depth'])
                                print(f"发现 {len(found_links)} 个链接")
                            except Exception as e:
                                print(f"链接挖掘失败: {str(e)}")
                        
                        print(f"\n抓取成功！文本长度: {len(web_content)}字符")
                        if image_resources:
                            print(f"发现 {len(image_resources)} 张图片")
                        input("\n按Enter返回主菜单...")
                        break
                        
            elif choice == '2':  # 预览抓取的文本
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
                    
                    if image_resources:
                        print(f"\n{' 发现图片 ':-^50}")
                        for i, img in enumerate(image_resources[:3], 1):
                            print(f"{i}. {img[:60]}{'...' if len(img) > 60 else ''}")
                        if len(image_resources) > 3:
                            print(f"...显示前3/{len(image_resources)}张图片")
                    
                    input("\n按Enter返回主菜单...")
                    
            elif choice == '3':  # 保存文本到文件
                if not web_content:
                    print("\n没有可保存的文本内容！")
                    input("按Enter继续...")
                else:
                    filename, error = save_to_file(web_content, current_url, "text")
                    if error:
                        print(error)
                    else:
                        abs_path = os.path.abspath(filename)
                        print(f"保存成功！文件位置: {abs_path}")
                    input("\n按Enter返回主菜单...")
                    
            elif choice == '4':  # 下载图片资源
                if not image_resources:
                    print("\n没有可下载的图片资源！")
                    input("按Enter继续...")
                else:
                    clear_screen()
                    print(f"\n{' 图片资源列表 ':=^50}")
                    for i, img_url in enumerate(image_resources, 1):
                        print(f"{i}. {img_url[:80]}{'...' if len(img_url) > 80 else ''}")
                    print(f"共发现 {len(image_resources)} 张图片")
                    print("\n输入要下载的图片编号（1-N）")
                    print("输入 a 下载全部图片")
                    print("输入 s 保存图片链接到文件")
                    print("输入 b 返回主菜单")
                    
                    while True:
                        choice = input("\n>>> ").strip().lower()
                        
                        if choice == 'b':
                            break
                            
                        elif choice == 'a':
                            print(f"开始下载所有 {len(image_resources)} 张图片...")
                            success = 0
                            errors = []
                            skipped = 0
                            
                            # 使用多线程下载
                            with concurrent.futures.ThreadPoolExecutor(
                                max_workers=CRAWL_SETTINGS['max_threads']
                            ) as executor:
                                # 创建任务列表
                                futures = [
                                    executor.submit(
                                        download_image, 
                                        img_url, 
                                        current_url, 
                                        i, 
                                        len(image_resources)
                                    )
                                    for i, img_url in enumerate(image_resources, 1)
                                ]
                                
                                # 处理任务结果
                                for future in concurrent.futures.as_completed(futures):
                                    filepath, error = future.result()
                                    if error:
                                        if "图片过大" in error:
                                            skipped += 1
                                        else:
                                            errors.append(error)
                                        print(f"下载失败: {error}")
                                    else:
                                        print(f"下载成功: {filepath}")
                                        success += 1
                            
                            print(f"\n下载完成! 成功: {success}, 失败: {len(errors)}, 跳过: {skipped}")
                            if errors:
                                print("错误列表 (前5个):")
                                for e in errors[:5]:
                                    print(f" - {e}")
                            input("\n按Enter返回图片菜单...")
                            break
                            
                        elif choice == 's':
                            filename, error = save_to_file(image_resources, current_url, "image_list")
                            if error:
                                print(error)
                            else:
                                abs_path = os.path.abspath(filename)
                                print(f"图片链接已保存到: {abs_path}")
                            input("\n按Enter返回图片菜单...")
                            break
                        
                        elif choice.isdigit():
                            index = int(choice) - 1
                            if 0 <= index < len(image_resources):
                                img_url = image_resources[index]
                                print(f"\n开始下载: {img_url}")
                                filepath, error = download_image(img_url, current_url)
                                if error:
                                    print(f"下载失败: {error}")
                                else:
                                    print(f"下载成功: {filepath}")
                            else:
                                print("无效的图片编号!")
                            input("\n按Enter返回图片菜单...")
                            break
                        
                        else:
                            print("无效输入! 请重新选择")
                    
            elif choice == '5':  # 高级设置
                advanced_settings()
                
            elif choice == '6':  # 清除当前数据
                current_url = None
                web_content = None
                image_resources = []
                found_links = []
                print("\n数据已重置!")
                input("按Enter继续...")
                
            else:
                print("\n无效输入！请选择1-6")
                input("按Enter继续...")
                
        except Exception as e:
            logging.error(f"主循环异常: {str(e)}")
            print(f"发生错误: {str(e)}")
            input("按Enter继续...")

if __name__ == "__main__":
    main()
