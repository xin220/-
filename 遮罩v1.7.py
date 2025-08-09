import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import time
import sys
import os
import re
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
import concurrent.futures
import shutil
import html
import chardet
import fake_useragent
import cloudscraper
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver import ChromeOptions
import redis
import brotli
from curl_cffi import requests as curl_requests
from readability import Document
from lxml.html import fromstring
import numpy as np
from sklearn.ensemble import IsolationForest

warnings.filterwarnings("ignore")  # 忽略SSL警告

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='crawler.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

# 全局爬取设置
CRAWL_SETTINGS = {
    'retry_times': 3,
    'use_proxy': False,
    'proxy': None,
    'proxy_list': [],
    'current_proxy_index': 0,
    'ignore_ssl': False,
    'dynamic_rendering': False,
    'request_delay': 0.5,
    'max_depth': 1,
    'image_crawling': True,
    'max_threads': 5,
    'image_size_limit': 10,
    'text_crawling': True,
    'use_cookies': False,
    'use_cloudscraper': False,
    'timeout': (10, 30),  # (连接超时, 读取超时)
    'redis_host': 'localhost',
    'redis_port': 6379,
    'redis_db': 0,
    'redis_password': '',
    'use_distributed': False,
    'use_bloom_filter': True,
    'behavior_simulation': True,
    'tls_fingerprint': True,
    'ai_content_extraction': True,
    'anomaly_detection': True,
}

# Redis连接池
redis_pool = redis.ConnectionPool(
    host=CRAWL_SETTINGS['redis_host'],
    port=CRAWL_SETTINGS['redis_port'],
    db=CRAWL_SETTINGS['redis_db'],
    password=CRAWL_SETTINGS['redis_password'],
    decode_responses=True
)

# 增强版User-Agent列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Whale/3.24.223.18 Safari/537.36',
    # 添加更多现代浏览器UA
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/119.0',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
]

# 常用Referer列表
REFERERS = [
    'https://www.google.com/',
    'https://www.bing.com/',
    'https://duckduckgo.com/',
    'https://www.yahoo.com/',
    'https://www.baidu.com/',
    'https://yandex.com/',
    'https://www.ecosia.org/',
]

def get_random_ua():
    try:
        # 使用fake_useragent库获取随机UA
        ua = fake_useragent.UserAgent().random
        return ua
    except:
        # 如果获取失败，使用本地列表
        return random.choice(USER_AGENTS)

def get_random_referer():
    return random.choice(REFERERS)

def validate_url(url):
    parsed = urlparse.urlparse(url)
    if not parsed.scheme:
        url = 'http://' + url
    
    # 验证URL格式
    if not re.match(r'^https?://[^\s/$.?#].[^\s]*$', url):
        return None
    
    return url

def get_robots_permission(url):
    parsed = urlparse.urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    rp = RobotFileParser()
    rp.set_url(urlparse.urljoin(base_url, "/robots.txt"))
    try:
        rp.read()
        return rp.can_fetch("*", url)
    except Exception as e:
        logging.warning(f"无法获取robots.txt: {str(e)}")
        # 如果无法获取robots.txt，默认允许爬取
        return True

def rotate_proxy():
    """轮换使用代理列表中的下一个代理"""
    if not CRAWL_SETTINGS['proxy_list']:
        return None
    
    CRAWL_SETTINGS['current_proxy_index'] = (CRAWL_SETTINGS['current_proxy_index'] + 1) % len(CRAWL_SETTINGS['proxy_list'])
    return CRAWL_SETTINGS['proxy_list'][CRAWL_SETTINGS['current_proxy_index']]

def get_current_proxy():
    """获取当前使用的代理"""
    if not CRAWL_SETTINGS['use_proxy']:
        return None
    
    if CRAWL_SETTINGS['proxy_list']:
        return CRAWL_SETTINGS['proxy_list'][CRAWL_SETTINGS['current_proxy_index']]
    
    return CRAWL_SETTINGS['proxy']

def test_proxy(proxy):
    """测试代理是否可用"""
    test_url = "http://httpbin.org/ip"
    try:
        response = requests.get(test_url, proxies={"http": proxy, "https": proxy}, timeout=10)
        if response.status_code == 200:
            return True
    except:
        pass
    return False

def requests_retry_session():
    session = requests.Session()
    retry = Retry(
        total=CRAWL_SETTINGS['retry_times'],
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504, 429, 403, 404, 408],
        allowed_methods=['GET', 'POST'],
        respect_retry_after_header=True
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    # 添加自定义请求头
    session.headers.update({
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'TE': 'Trailers',
    })
    
    return session

def get_redis_connection():
    """获取Redis连接"""
    try:
        return redis.Redis(
            host=CRAWL_SETTINGS['redis_host'],
            port=CRAWL_SETTINGS['redis_port'],
            db=CRAWL_SETTINGS['redis_db'],
            password=CRAWL_SETTINGS['redis_password'],
            decode_responses=True
        )
    except Exception as e:
        logging.error(f"Redis连接失败: {str(e)}")
        return None

def url_seen(url):
    """检查URL是否已爬取（使用Redis Bloom Filter）"""
    if not CRAWL_SETTINGS['use_bloom_filter'] or not CRAWL_SETTINGS['use_distributed']:
        return False
    
    r = get_redis_connection()
    if not r:
        return False
    
    try:
        return r.execute_command('BF.EXISTS', 'urls:bloom', url) == 1
    except:
        # 如果Bloom Filter不可用，使用普通集合
        return r.sismember('urls:seen', url)

def mark_url_seen(url):
    """标记URL为已爬取"""
    if not CRAWL_SETTINGS['use_bloom_filter'] or not CRAWL_SETTINGS['use_distributed']:
        return
    
    r = get_redis_connection()
    if not r:
        return
    
    try:
        r.execute_command('BF.ADD', 'urls:bloom', url)
    except:
        # 如果Bloom Filter不可用，使用普通集合
        r.sadd('urls:seen', url)

def add_url_to_queue(url):
    """添加URL到Redis队列"""
    if not CRAWL_SETTINGS['use_distributed']:
        return
    
    r = get_redis_connection()
    if not r:
        return
    
    try:
        r.lpush('spider:start_urls', url)
    except Exception as e:
        logging.error(f"添加URL到队列失败: {str(e)}")

def get_url_from_queue():
    """从Redis队列获取URL"""
    if not CRAWL_SETTINGS['use_distributed']:
        return None
    
    r = get_redis_connection()
    if not r:
        return None
    
    try:
        return r.rpop('spider:start_urls')
    except Exception as e:
        logging.error(f"从队列获取URL失败: {str(e)}")
        return None

def simulate_behavior(page):
    """模拟人类行为模式"""
    if not CRAWL_SETTINGS['behavior_simulation']:
        return
    
    try:
        # 随机移动鼠标
        width = page.evaluate("document.body.scrollWidth")
        height = page.evaluate("document.body.scrollHeight")
        
        # 生成随机轨迹
        num_movements = random.randint(5, 15)
        for i in range(num_movements):
            x = random.randint(0, width)
            y = random.randint(0, height)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.1, 0.5))
        
        # 随机滚动
        for _ in range(random.randint(3, 8)):
            scroll_y = random.randint(200, 800)
            page.mouse.wheel(0, scroll_y)
            time.sleep(random.uniform(0.2, 1.0))
            
        # 随机点击
        if random.random() < 0.3:
            page.mouse.click(button="left")
            time.sleep(random.uniform(0.5, 1.5))
    except Exception as e:
        logging.warning(f"行为模拟失败: {str(e)}")

def render_dynamic_page(url):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, WebDriverException
    except ImportError:
        logging.error("未安装Selenium，无法使用动态渲染")
        return None
    
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"user-agent={get_random_ua()}")
        
        # 禁用自动化控制标志
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 设置更自然的浏览器指纹
        caps = DesiredCapabilities.CHROME
        caps['goog:loggingPrefs'] = {'performance': 'ALL'}
        
        # 添加代理设置
        if CRAWL_SETTINGS['use_proxy']:
            proxy = get_current_proxy()
            if proxy:
                options.add_argument(f'--proxy-server={proxy}')
        
        driver = webdriver.Chrome(options=options, desired_capabilities=caps)
        
        # 隐藏自动化特征
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        driver.set_page_load_timeout(30)
        driver.get(url)
        
        try:
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
        except TimeoutException:
            logging.warning("页面加载超时，继续处理已加载内容")
        
        # 模拟人类行为
        if CRAWL_SETTINGS['behavior_simulation']:
            # 随机移动鼠标
            width = driver.execute_script("return document.body.scrollWidth")
            height = driver.execute_script("return document.body.scrollHeight")
            
            # 生成随机轨迹
            num_movements = random.randint(5, 15)
            for i in range(num_movements):
                x = random.randint(0, width)
                y = random.randint(0, height)
                driver.execute_script(f"document.elementFromPoint({x}, {y}).scrollIntoView()")
                time.sleep(random.uniform(0.1, 0.5))
            
            # 随机滚动
            for _ in range(random.randint(3, 8)):
                scroll_y = random.randint(200, 800)
                driver.execute_script(f"window.scrollBy(0, {scroll_y})")
                time.sleep(random.uniform(0.2, 1.0))
                
            # 随机点击
            if random.random() < 0.3:
                elements = driver.find_elements(By.XPATH, "//a | //button")
                if elements:
                    random.choice(elements).click()
                    time.sleep(random.uniform(0.5, 1.5))
        
        content = driver.page_source
        driver.quit()
        return content
    except Exception as e:
        logging.error(f"动态渲染失败: {str(e)}")
        try:
            driver.quit()
        except:
            pass
        return None

def find_image_resources(soup, base_url):
    image_links = set()
    
    for img in soup.find_all('img', src=True):
        src = img['src'].strip()
        if src and not src.lower().startswith('data:'):
            # 处理相对URL
            try:
                full_url = urlparse.urljoin(base_url, src)
                image_links.add(full_url)
            except:
                continue
    
    # 检查CSS背景图
    for element in soup.find_all(style=True):
        style = element['style']
        matches = re.findall(r'url\(["\']?(.*?)["\']?\)', style, re.IGNORECASE)
        for url in matches:
            if url.startswith('data:'):
                continue
            try:
                full_url = urlparse.urljoin(base_url, url)
                image_links.add(full_url)
            except:
                continue
    
    # 检查link标签中的图标
    for link in soup.find_all('link', rel=['icon', 'apple-touch-icon', 'shortcut icon'], href=True):
        href = link['href'].strip()
        if href and not href.lower().startswith('data:'):
            try:
                full_url = urlparse.urljoin(base_url, href)
                image_links.add(full_url)
            except:
                continue
    
    # 检查meta标签中的OG图片
    for meta in soup.find_all('meta', attrs={'property': 'og:image', 'content': True}):
        content = meta['content'].strip()
        if content and not content.lower().startswith('data:'):
            try:
                full_url = urlparse.urljoin(base_url, content)
                image_links.add(full_url)
            except:
                continue
    
    return list(image_links)

def extract_links(soup, base_url, max_depth):
    links = set()
    parsed_base = urlparse.urlparse(base_url)
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href or href.startswith(('#', 'javascript:', 'mailto:')):
            continue
        
        try:
            full_url = urlparse.urljoin(base_url, href)
            parsed = urlparse.urlparse(full_url)
            
            # 只保留http/https链接
            if parsed.scheme not in ['http', 'https']:
                continue
            
            # 过滤非文本内容
            if any(ext in parsed.path.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.zip', '.rar', '.exe', '.mp3', '.mp4']):
                continue
            
            # 只保留同域名链接
            if parsed.netloc == parsed_base.netloc:
                links.add(full_url)
        except:
            continue
    
    return list(links)[:10 * max_depth]

def fetch_web_content(url):
    time.sleep(random.uniform(CRAWL_SETTINGS['request_delay'], CRAWL_SETTINGS['request_delay'] * 2))
    
    # 检查URL是否已爬取（分布式模式）
    if CRAWL_SETTINGS['use_distributed'] and url_seen(url):
        logging.info(f"URL已爬取: {url}")
        return None, [], "URL已爬取"
    
    session = requests_retry_session()
    headers = {
        'User-Agent': get_random_ua(),
        'Referer': get_random_referer(),
        'DNT': '1',
    }
    
    proxies = None
    if CRAWL_SETTINGS['use_proxy']:
        proxy = get_current_proxy()
        if proxy:
            proxies = {
                'http': proxy,
                'https': proxy,
            }
    
    verify = not CRAWL_SETTINGS['ignore_ssl']
    content = None
    image_resources = []
    
    try:
        # 使用curl_cffi绕过TLS指纹检测
        if CRAWL_SETTINGS['tls_fingerprint']:
            try:
                response = curl_requests.get(
                    url,
                    impersonate="chrome110",  # 模拟Chrome指纹
                    headers=headers,
                    proxies=proxies,
                    verify=verify,
                    timeout=CRAWL_SETTINGS['timeout']
                )
                content = response.text
            except Exception as e:
                logging.warning(f"curl_cffi请求失败: {str(e)}")
        
        # 尝试使用cloudscraper绕过Cloudflare
        if not content and CRAWL_SETTINGS['use_cloudscraper']:
            try:
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url, timeout=CRAWL_SETTINGS['timeout'], proxies=proxies)
                content = response.text
            except Exception as e:
                logging.warning(f"cloudscraper失败: {str(e)}")
        
        # 如果以上方法都未获取内容，使用动态渲染或普通请求
        if not content and CRAWL_SETTINGS['dynamic_rendering']:
            content = render_dynamic_page(url)
        
        # 如果以上方法都未获取内容，使用普通请求
        if not content:
            response = session.get(
                url, 
                headers=headers, 
                timeout=CRAWL_SETTINGS['timeout'], 
                proxies=proxies,
                verify=verify
            )
            
            if response.status_code == 403 and 'cloudflare' in response.text.lower():
                # 遇到Cloudflare防护，尝试切换方法
                if not CRAWL_SETTINGS['use_cloudscraper']:
                    # 启用cloudscraper重试
                    CRAWL_SETTINGS['use_cloudscraper'] = True
                    return fetch_web_content(url)
                elif CRAWL_SETTINGS['use_proxy']:
                    # 切换代理
                    rotate_proxy()
                    return fetch_web_content(url)
            
            # 处理编码问题
            if not response.encoding or response.encoding.lower() == 'iso-8859-1':
                encoding_detected = chardet.detect(response.content)['encoding']
                if encoding_detected:
                    response.encoding = encoding_detected
            
            try:
                content = response.text
            except UnicodeDecodeError:
                content = response.content.decode('utf-8', errors='replace')
            
            if response.status_code != 200:
                return None, [], f"错误: HTTP状态码 {response.status_code}"
        
        try:
            soup = BeautifulSoup(content, 'lxml')
        except Exception:
            try:
                soup = BeautifulSoup(content, 'html.parser')
            except Exception as e:
                return None, [], f"解析失败: {str(e)}"
        
        if CRAWL_SETTINGS['image_crawling']:
            image_resources = find_image_resources(soup, url)
            logging.info(f"找到 {len(image_resources)} 张图片")
        
        text = ""
        if CRAWL_SETTINGS['text_crawling']:
            # 改进的内容提取方法
            text = extract_main_content(soup, url)
        
        # 标记URL为已爬取（分布式模式）
        if CRAWL_SETTINGS['use_distributed']:
            mark_url_seen(url)
        
        return text, image_resources, None
    
    except requests.exceptions.RequestException as e:
        # 网络请求错误，尝试切换代理
        if CRAWL_SETTINGS['use_proxy'] and CRAWL_SETTINGS['proxy_list']:
            rotate_proxy()
            return fetch_web_content(url)
        
        logging.error(f"抓取失败: {str(e)}")
        return None, [], f"抓取失败: {str(e)}"
    except Exception as e:
        logging.error(f"抓取失败: {str(e)}")
        return None, [], f"抓取失败: {str(e)}"

def extract_main_content(soup, url):
    """智能内容提取方法"""
    # 使用AI增强的内容提取
    if CRAWL_SETTINGS['ai_content_extraction']:
        try:
            # 使用Readability算法改进版
            doc = Document(str(soup))
            content_html = doc.summary()
            content_tree = fromstring(content_html)
            text = content_tree.text_content()
            
            # 如果内容太短，尝试其他方法
            if len(text) < 500:
                raise Exception("Readability提取内容过短")
                
            return clean_text(text)
        except Exception as e:
            logging.warning(f"AI内容提取失败: {str(e)}, 使用备用方法")
    
    # 尝试识别常见的内容区域
    content_selectors = [
        'article',
        'main',
        '.article',
        '.content',
        '.post-content',
        '.entry-content',
        '.story-content',
        '.article-body',
        '#article',
        '#content',
        '#main-content',
        '#post-content'
    ]
    
    for selector in content_selectors:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(separator='\n', strip=True)
            if len(text) > 500:  # 确保有足够内容
                return clean_text(text)
    
    # 如果未找到，使用启发式方法
    paragraphs = soup.find_all(['p', 'div'])
    text_candidates = []
    total_text = ""
    
    for p in paragraphs:
        if len(p.get_text(strip=True)) < 50:
            continue
        
        # 计算链接密度
        links = p.find_all('a')
        link_text_length = sum(len(a.get_text(strip=True)) for a in links)
        total_text_length = len(p.get_text(strip=True))
        link_density = link_text_length / total_text_length if total_text_length > 0 else 0
        
        if link_density < 0.3:
            text_candidates.append(p.get_text(strip=True))
            total_text += p.get_text(strip=True) + "\n\n"
    
    if text_candidates:
        return clean_text('\n\n'.join(text_candidates))
    
    # 最后手段：获取整个文本
    return clean_text(soup.get_text(separator='\n', strip=True))

def clean_text(text):
    """清理和格式化文本"""
    # 移除多余空行
    cleaned_text = re.sub(r'\n{3,}', '\n\n', text)
    # 转义HTML实体
    cleaned_text = html.unescape(cleaned_text)
    # 移除控制字符
    cleaned_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b]', '', cleaned_text)
    # 移除首尾空白
    cleaned_text = cleaned_text.strip()
    # 规范化空格
    cleaned_text = re.sub(r'[ \t]{2,}', ' ', cleaned_text)
    
    # 异常检测 - 识别可能的垃圾内容
    if CRAWL_SETTINGS['anomaly_detection'] and detect_anomaly(cleaned_text):
        logging.warning("检测到异常文本内容")
        return "警告：检测到可能无效的内容"
    
    return cleaned_text

def detect_anomaly(text):
    """使用孤立森林检测异常内容"""
    if len(text) < 100:
        return False
    
    try:
        # 创建特征向量：行数、平均行长、特殊字符比例、重复内容比例
        lines = text.split('\n')
        num_lines = len(lines)
        avg_line_length = sum(len(line) for line in lines) / num_lines
        
        special_chars = sum(1 for char in text if not char.isalnum() and not char.isspace())
        special_ratio = special_chars / len(text)
        
        # 检测重复内容
        chunks = [text[i:i+50] for i in range(0, len(text), 50)]
        unique_chunks = len(set(chunks))
        repetition_ratio = 1 - (unique_chunks / len(chunks))
        
        # 特征向量
        X = np.array([[num_lines, avg_line_length, special_ratio, repetition_ratio]])
        
        # 创建模型
        clf = IsolationForest(contamination=0.1, random_state=42)
        clf.fit(X)
        
        # 预测异常
        return clf.predict(X)[0] == -1
    except Exception as e:
        logging.warning(f"异常检测失败: {str(e)}")
        return False

def download_image(url, base_url, index=None, total=None):
    try:
        parsed = urlparse.urlparse(url)
        # 从URL中提取文件名，或生成哈希文件名
        filename = os.path.basename(parsed.path) 
        if not filename or '.' not in filename:
            ext = 'jpg'  # 默认扩展名
            # 尝试从URL路径中检测扩展名
            if '.' in parsed.path:
                ext = parsed.path.split('.')[-1].lower()[:4]
            filename = f"image_{hashlib.md5(url.encode()).hexdigest()[:8]}.{ext}"
        
        # 创建安全的目录名
        domain = re.sub(r'[^\w\-]', '_', urlparse.urlparse(base_url).netloc.replace('www.', ''))
        image_dir = f"{domain}_images"
        os.makedirs(image_dir, exist_ok=True)
        filepath = os.path.join(image_dir, filename)
        
        headers = {
            'User-Agent': get_random_ua(),
            'Referer': base_url,
        }
        
        proxies = None
        if CRAWL_SETTINGS['use_proxy']:
            proxy = get_current_proxy()
            if proxy:
                proxies = {
                    'http': proxy,
                    'https': proxy,
                }
        
        # 检查图片大小限制
        try:
            head_response = requests.head(
                url, 
                headers=headers, 
                timeout=(5, 10), 
                proxies=proxies,
                allow_redirects=True
            )
            
            if 'Content-Length' in head_response.headers:
                file_size = int(head_response.headers['Content-Length']) / (1024 * 1024)
                if file_size > CRAWL_SETTINGS['image_size_limit']:
                    return None, f"图片过大({file_size:.2f}MB > {CRAWL_SETTINGS['image_size_limit']}MB)，跳过下载"
        except:
            pass  # 如果HEAD请求失败，继续尝试GET
        
        # 下载图片
        with requests.get(
            url, 
            headers=headers, 
            timeout=(10, 30), 
            proxies=proxies,
            stream=True
        ) as response:
            if response.status_code != 200:
                return None, f"下载失败: HTTP {response.status_code}"
            
            # 再次检查大小（如果HEAD失败）
            if 'Content-Length' in response.headers:
                file_size = int(response.headers['Content-Length']) / (1024 * 1024)
                if file_size > CRAWL_SETTINGS['image_size_limit']:
                    return None, f"图片过大({file_size:.2f}MB > {CRAWL_SETTINGS['image_size_limit']}MB)，跳过下载"
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        # 验证下载的文件
        if os.path.getsize(filepath) < 1024:  # 小于1KB可能是错误
            os.remove(filepath)
            return None, "图片文件过小，可能下载失败"
        
        if index is not None and total is not None:
            return filepath, f"成功 [{index}/{total}]"
        return filepath, None
    
    except Exception as e:
        logging.error(f"图片下载失败: {str(e)}")
        return None, f"图片下载失败: {str(e)}"

def save_to_file(content, base_url, file_type="text"):
    domain = re.sub(r'[^\w\-]', '_', urlparse.urlparse(base_url).netloc.replace('www.', ''))
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

class CrawlerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("遮罩爬虫系统 v1.7")
        self.root.geometry("900x750")
        self.root.resizable(True, True)
        
        # 状态变量
        self.current_url = None
        self.web_content = None
        self.image_resources = []
        self.found_links = []
        self.is_crawling = False
        self.downloading_images = False
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=CRAWL_SETTINGS['max_threads'])
        
        # 创建UI
        self.create_widgets()
        
        # 尝试加载配置
        try:
            with open('crawler_config.json', 'r') as f:
                loaded_settings = json.load(f)
                # 合并设置，保留未加载的默认设置
                CRAWL_SETTINGS.update(loaded_settings)
        except:
            pass
            
        # 添加右下角署名
        self.create_signature()
        
        # 初始化Redis连接
        if CRAWL_SETTINGS['use_distributed']:
            self.log_message("分布式模式已启用")
    
    def create_signature(self):
        signature = tk.Label(self.root, text="by 电脑人", fg="gray", font=("Arial", 8))
        signature.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

    def create_widgets(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # URL输入部分
        url_frame = ttk.LabelFrame(main_frame, text="URL输入", padding=10)
        url_frame.pack(fill=tk.X, pady=5)
        
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=70)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        crawl_btn = ttk.Button(url_frame, text="开始抓取", command=self.start_crawling)
        crawl_btn.pack(side=tk.LEFT)
        
        # 分布式模式按钮
        self.distributed_btn = ttk.Button(url_frame, text="分布式模式", command=self.toggle_distributed)
        self.distributed_btn.pack(side=tk.RIGHT, padx=5)
        
        # 状态和结果展示部分
        result_frame = ttk.Frame(main_frame)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 状态面板
        status_frame = ttk.LabelFrame(result_frame, text="抓取状态", padding=10)
        status_frame.pack(fill=tk.X, pady=5)
        
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(status_frame, textvariable=self.status_var)
        status_label.pack(anchor=tk.W)
        
        # Redis状态
        self.redis_status_var = tk.StringVar(value="Redis: 未连接")
        redis_status_label = ttk.Label(status_frame, textvariable=self.redis_status_var)
        redis_status_label.pack(anchor=tk.W)
        
        # 结果文本预览
        text_frame = ttk.LabelFrame(result_frame, text="文本预览", padding=10)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.text_preview = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=10)
        self.text_preview.pack(fill=tk.BOTH, expand=True)
        
        # 图片资源部分
        image_frame = ttk.LabelFrame(result_frame, text="图片资源", padding=10)
        image_frame.pack(fill=tk.X, pady=5)
        
        # 图片列表
        image_list_frame = ttk.Frame(image_frame)
        image_list_frame.pack(fill=tk.X, pady=5)
        
        self.image_listbox = tk.Listbox(image_list_frame, height=6)
        self.image_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        scrollbar = ttk.Scrollbar(image_list_frame, orient=tk.VERTICAL, command=self.image_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.image_listbox.config(yscrollcommand=scrollbar.set)
        
        # 图片操作按钮
        image_btn_frame = ttk.Frame(image_frame)
        image_btn_frame.pack(fill=tk.X, pady=5)
        
        download_btn = ttk.Button(image_btn_frame, text="下载选中图片", command=self.download_selected_image)
        download_btn.pack(side=tk.LEFT, padx=5)
        
        download_all_btn = ttk.Button(image_btn_frame, text="下载全部图片", command=self.download_all_images)
        download_all_btn.pack(side=tk.LEFT, padx=5)
        
        save_links_btn = ttk.Button(image_btn_frame, text="保存图片链接", command=self.save_image_links)
        save_links_btn.pack(side=tk.LEFT, padx=5)
        
        # 操作按钮部分
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=10)
        
        save_text_btn = ttk.Button(action_frame, text="保存文本", command=self.save_text)
        save_text_btn.pack(side=tk.LEFT, padx=5)
        
        save_links_btn = ttk.Button(action_frame, text="保存链接", command=self.save_links)
        save_links_btn.pack(side=tk.LEFT, padx=5)
        
        advanced_btn = ttk.Button(action_frame, text="高级设置", command=self.open_advanced_settings)
        advanced_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = ttk.Button(action_frame, text="清除数据", command=self.clear_data)
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        # 队列操作按钮
        queue_frame = ttk.Frame(action_frame)
        queue_frame.pack(side=tk.RIGHT, padx=5)
        
        queue_add_btn = ttk.Button(queue_frame, text="添加到队列", command=self.add_to_queue)
        queue_add_btn.pack(side=tk.LEFT, padx=2)
        
        queue_get_btn = ttk.Button(queue_frame, text="从队列获取", command=self.get_from_queue)
        queue_get_btn.pack(side=tk.LEFT, padx=2)
        
        # 日志输出
        log_frame = ttk.LabelFrame(main_frame, text="日志", padding=10)
        log_frame.pack(fill=tk.BOTH, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)
    
    def toggle_distributed(self):
        """切换分布式模式"""
        CRAWL_SETTINGS['use_distributed'] = not CRAWL_SETTINGS['use_distributed']
        if CRAWL_SETTINGS['use_distributed']:
            self.distributed_btn.config(text="关闭分布式")
            self.log_message("分布式模式已启用")
            
            # 测试Redis连接
            r = get_redis_connection()
            if r:
                try:
                    r.ping()
                    self.redis_status_var.set("Redis: 已连接")
                except:
                    self.redis_status_var.set("Redis: 连接失败")
        else:
            self.distributed_btn.config(text="分布式模式")
            self.log_message("分布式模式已禁用")
            self.redis_status_var.set("Redis: 未连接")
    
    def add_to_queue(self):
        """添加URL到分布式队列"""
        if not CRAWL_SETTINGS['use_distributed']:
            messagebox.showwarning("警告", "请先启用分布式模式")
            return
            
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("警告", "请输入URL")
            return
            
        valid_url = validate_url(url)
        if not valid_url:
            messagebox.showerror("错误", "无效的URL")
            return
            
        add_url_to_queue(valid_url)
        self.log_message(f"已添加到队列: {valid_url}")
        messagebox.showinfo("成功", "URL已添加到分布式队列")
    
    def get_from_queue(self):
        """从分布式队列获取URL"""
        if not CRAWL_SETTINGS['use_distributed']:
            messagebox.showwarning("警告", "请先启用分布式模式")
            return
            
        url = get_url_from_queue()
        if url:
            self.url_var.set(url)
            self.log_message(f"从队列获取URL: {url}")
            self.start_crawling()
        else:
            messagebox.showinfo("提示", "队列中没有URL")
    
    def log_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def start_crawling(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入URL")
            return
        
        if self.is_crawling:
            messagebox.showwarning("警告", "爬取操作正在进行中")
            return
        
        valid_url = validate_url(url)
        if not valid_url:
            messagebox.showerror("错误", "无效的URL！请包含http://或https://")
            return
        
        if not get_robots_permission(valid_url):
            proceed = messagebox.askyesno("警告", "该网站禁止爬虫抓取！继续操作可能违反服务条款。\n仍要继续吗？")
            if not proceed:
                return
        
        self.current_url = valid_url
        self.is_crawling = True
        self.status_var.set(f"正在抓取: {self.current_url}")
        self.log_message(f"开始抓取: {self.current_url}")
        
        # 在子线程中执行爬取操作
        threading.Thread(target=self.crawl_thread, daemon=True).start()
    
    def crawl_thread(self):
        self.web_content, self.image_resources, error = fetch_web_content(self.current_url)
        
        if error:
            self.log_message(f"抓取失败: {error}")
            self.status_var.set(f"抓取失败: {error}")
            self.is_crawling = False
            return
        
        # 更新文本预览
        self.text_preview.config(state=tk.NORMAL)
        self.text_preview.delete(1.0, tk.END)
        self.text_preview.insert(tk.END, self.web_content[:2000] + ("" if len(self.web_content) <= 2000 else "..."))
        self.text_preview.config(state=tk.DISABLED)
        
        # 更新图片列表
        self.image_listbox.delete(0, tk.END)
        for img_url in self.image_resources:
            display_url = img_url[:80] + "..." if len(img_url) > 80 else img_url
            self.image_listbox.insert(tk.END, display_url)
        
        # 链接挖掘
        if CRAWL_SETTINGS['max_depth'] > 0:
            self.log_message("正在挖掘页面链接...")
            try:
                if not self.web_content:
                    session = requests_retry_session()
                    headers = {'User-Agent': get_random_ua()}
                    proxies = None
                    if CRAWL_SETTINGS['use_proxy'] and CRAWL_SETTINGS['proxy_list']:
                        proxy = get_current_proxy()
                        if proxy:
                            proxies = {
                                'http': proxy,
                                'https': proxy,
                            }
                    response = session.get(
                        self.current_url, 
                        headers=headers, 
                        proxies=proxies,
                        verify=not CRAWL_SETTINGS['ignore_ssl']
                    )
                    content = response.text
                else:
                    content = self.web_content
                
                soup = BeautifulSoup(content, 'lxml')
                self.found_links = extract_links(soup, self.current_url, CRAWL_SETTINGS['max_depth'])
                self.log_message(f"发现 {len(self.found_links)} 个链接")
            except Exception as e:
                self.log_message(f"链接挖掘失败: {str(e)}")
        
        self.log_message(f"抓取成功！文本长度: {len(self.web_content)}字符")
        if self.image_resources:
            self.log_message(f"发现 {len(self.image_resources)} 张图片")
        
        # 如果是分布式模式，添加发现的链接到队列
        if CRAWL_SETTINGS['use_distributed'] and self.found_links:
            for link in self.found_links:
                add_url_to_queue(link)
            self.log_message(f"已添加 {len(self.found_links)} 个链接到分布式队列")
        
        self.status_var.set(f"抓取完成: {self.current_url}")
        self.is_crawling = False
    
    def download_selected_image(self):
        if not self.image_resources:
            messagebox.showwarning("警告", "没有可下载的图片资源")
            return
        
        selected_indices = self.image_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("警告", "请选择要下载的图片")
            return
        
        index = selected_indices[0]
        img_url = self.image_resources[index]
        
        if self.downloading_images:
            messagebox.showwarning("警告", "图片下载正在进行中")
            return
        
        self.downloading_images = True
        self.log_message(f"开始下载图片: {img_url[:80]}{'...' if len(img_url) > 80 else ''}")
        self.status_var.set("正在下载图片...")
        
        threading.Thread(target=self.download_image_thread, args=(img_url,), daemon=True).start()
    
    def download_image_thread(self, img_url):
        filepath, error = download_image(img_url, self.current_url)
        
        if error:
            self.log_message(f"下载失败: {error}")
        else:
            self.log_message(f"下载成功: {filepath}")
            messagebox.showinfo("成功", f"图片已保存到:\n{os.path.abspath(filepath)}")
        
        self.status_var.set("图片下载完成")
        self.downloading_images = False
    
    def download_all_images(self):
        if not self.image_resources:
            messagebox.showwarning("警告", "没有可下载的图片资源")
            return
            
        if self.downloading_images:
            messagebox.showwarning("警告", "图片下载正在进行中")
            return
            
        self.downloading_images = True
        self.log_message(f"开始下载所有 {len(self.image_resources)} 张图片...")
        self.status_var.set("正在下载图片...")
        self.progress_var.set(0)
        
        threading.Thread(target=self.download_all_images_thread, daemon=True).start()
    
    def download_all_images_thread(self):
        success = 0
        errors = []
        skipped = 0
        
        total = len(self.image_resources)
        for i, img_url in enumerate(self.image_resources, 1):
            filepath, error = download_image(img_url, self.current_url, i, total)
            
            # 更新进度条
            progress = (i / total) * 100
            self.progress_var.set(progress)
            self.root.update_idletasks()
            
            if error:
                if "图片过大" in error:
                    skipped += 1
                    self.log_message(f"跳过图片 #{i}: {error}")
                else:
                    errors.append(error)
                    self.log_message(f"下载失败 #{i}: {error}")
            else:
                success += 1
                self.log_message(f"下载成功 #{i}: {filepath}")
        
        self.log_message(f"下载完成! 成功: {success}, 失败: {len(errors)}, 跳过: {skipped}")
        if errors:
            self.log_message("错误列表 (前5个):")
            for e in errors[:5]:
                self.log_message(f" - {e}")
        
        messagebox.showinfo("下载完成", f"图片下载完成!\n成功: {success}, 失败: {len(errors)}, 跳过: {skipped}")
        self.status_var.set("图片下载完成")
        self.progress_var.set(0)
        self.downloading_images = False
    
    def save_image_links(self):
        if not self.image_resources:
            messagebox.showwarning("警告", "没有图片链接可保存")
            return
            
        filename, error = save_to_file(self.image_resources, self.current_url, "image_list")
        if error:
            messagebox.showerror("保存失败", error)
        else:
            abs_path = os.path.abspath(filename)
            messagebox.showinfo("保存成功", f"图片链接已保存到:\n{abs_path}")
            self.log_message(f"图片链接已保存: {abs_path}")
    
    def save_text(self):
        if not self.web_content:
            messagebox.showwarning("警告", "没有文本内容可保存")
            return
            
        filename, error = save_to_file(self.web_content, self.current_url, "text")
        if error:
            messagebox.showerror("保存失败", error)
        else:
            abs_path = os.path.abspath(filename)
            messagebox.showinfo("保存成功", f"文本已保存到:\n{abs_path}")
            self.log_message(f"文本已保存: {abs_path}")
    
    def save_links(self):
        if not self.found_links:
            messagebox.showwarning("警告", "没有链接可保存")
            return
            
        filename, error = save_to_file(self.found_links, self.current_url, "links")
        if error:
            messagebox.showerror("保存失败", error)
        else:
            abs_path = os.path.abspath(filename)
            messagebox.showinfo("保存成功", f"链接已保存到:\n{abs_path}")
            self.log_message(f"链接已保存: {abs_path}")
    
    def open_advanced_settings(self):
        if hasattr(self, 'adv_window') and self.adv_window.winfo_exists():
            self.adv_window.lift()
            return
            
        self.adv_window = tk.Toplevel(self.root)
        self.adv_window.title("高级设置")
        self.adv_window.geometry("500x600")
        self.adv_window.resizable(False, False)
        
        AdvancedSettingsWindow(self.adv_window, self.log_message)
    
    def clear_data(self):
        self.current_url = None
        self.web_content = None
        self.image_resources = []
        self.found_links = []
        
        self.url_var.set("")
        self.text_preview.config(state=tk.NORMAL)
        self.text_preview.delete(1.0, tk.END)
        self.text_preview.config(state=tk.DISABLED)
        self.image_listbox.delete(0, tk.END)
        self.status_var.set("数据已重置")
        self.log_message("已清除所有数据")
        self.progress_var.set(0)
        
        messagebox.showinfo("清除完成", "所有数据已成功清除")

class AdvancedSettingsWindow:
    def __init__(self, parent, log_callback):
        self.parent = parent
        self.log_callback = log_callback
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.parent, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 设置项框架
        settings_frame = ttk.LabelFrame(main_frame, text="爬虫设置", padding=10)
        settings_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 1. 重试次数
        ttk.Label(settings_frame, text="重试次数 (0-5):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.retry_var = tk.IntVar(value=CRAWL_SETTINGS['retry_times'])
        ttk.Spinbox(settings_frame, from_=0, to=5, width=5, textvariable=self.retry_var).grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        # 2. 使用代理
        self.use_proxy_var = tk.BooleanVar(value=CRAWL_SETTINGS['use_proxy'])
        ttk.Checkbutton(settings_frame, text="使用代理", variable=self.use_proxy_var).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        
        ttk.Label(settings_frame, text="代理列表 (每行一个):").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        
        self.proxy_text = scrolledtext.ScrolledText(settings_frame, height=3, width=40)
        self.proxy_text.grid(row=3, column=0, columnspan=2, sticky="we", padx=5, pady=5)
        self.proxy_text.insert(tk.END, "\n".join(CRAWL_SETTINGS['proxy_list']))
        
        # 3. 忽略SSL验证
        self.ignore_ssl_var = tk.BooleanVar(value=CRAWL_SETTINGS['ignore_ssl'])
        ttk.Checkbutton(settings_frame, text="忽略SSL验证", variable=self.ignore_ssl_var).grid(row=4, column=0, sticky="w", padx=5, pady=5)
        
        # 4. 动态渲染
        self.dynamic_rendering_var = tk.BooleanVar(value=CRAWL_SETTINGS['dynamic_rendering'])
        ttk.Checkbutton(settings_frame, text="动态渲染(需Selenium)", variable=self.dynamic_rendering_var).grid(row=5, column=0, sticky="w", padx=5, pady=5)
        
        # 5. 请求延迟
        ttk.Label(settings_frame, text="请求延迟(秒):").grid(row=6, column=0, sticky="w", padx=5, pady=5)
        self.delay_var = tk.DoubleVar(value=CRAWL_SETTINGS['request_delay'])
        ttk.Spinbox(settings_frame, from_=0.0, to=5.0, increment=0.1, width=5, textvariable=self.delay_var).grid(row=6, column=1, sticky="w", padx=5, pady=5)
        
        # 6. 链接挖掘深度
        ttk.Label(settings_frame, text="链接挖掘深度 (0-3):").grid(row=7, column=0, sticky="w", padx=5, pady=5)
        self.depth_var = tk.IntVar(value=CRAWL_SETTINGS['max_depth'])
        ttk.Spinbox(settings_frame, from_=0, to=3, width=5, textvariable=self.depth_var).grid(row=7, column=1, sticky="w", padx=5, pady=5)
        
        # 7. 图片爬取
        self.image_crawling_var = tk.BooleanVar(value=CRAWL_SETTINGS['image_crawling'])
        ttk.Checkbutton(settings_frame, text="图片爬取", variable=self.image_crawling_var).grid(row=8, column=0, sticky="w", padx=5, pady=5)
        
        # 8. 最大线程数
        ttk.Label(settings_frame, text="最大下载线程数 (1-20):").grid(row=9, column=0, sticky="w", padx=5, pady=5)
        self.threads_var = tk.IntVar(value=CRAWL_SETTINGS['max_threads'])
        ttk.Spinbox(settings_frame, from_=1, to=20, width=5, textvariable=self.threads_var).grid(row=9, column=1, sticky="w", padx=5, pady=5)
        
        # 9. 图片大小限制
        ttk.Label(settings_frame, text="图片大小限制(MB):").grid(row=10, column=0, sticky="w", padx=5, pady=5)
        self.size_var = tk.IntVar(value=CRAWL_SETTINGS['image_size_limit'])
        ttk.Spinbox(settings_frame, from_=1, to=100, width=5, textvariable=self.size_var).grid(row=10, column=1, sticky="w", padx=5, pady=5)
        
        # 10. 文本爬取
        self.text_crawling_var = tk.BooleanVar(value=CRAWL_SETTINGS['text_crawling'])
        ttk.Checkbutton(settings_frame, text="文本爬取", variable=self.text_crawling_var).grid(row=11, column=0, sticky="w", padx=5, pady=5)
        
        # 11. 使用Cloudscraper
        self.cloudscraper_var = tk.BooleanVar(value=CRAWL_SETTINGS['use_cloudscraper'])
        ttk.Checkbutton(settings_frame, text="使用Cloudscraper (绕过Cloudflare)", variable=self.cloudscraper_var).grid(row=12, column=0, sticky="w", padx=5, pady=5)
        
        # 12. 超时设置
        ttk.Label(settings_frame, text="连接超时(秒):").grid(row=13, column=0, sticky="w", padx=5, pady=5)
        self.connect_timeout_var = tk.IntVar(value=CRAWL_SETTINGS['timeout'][0])
        ttk.Spinbox(settings_frame, from_=1, to=60, width=5, textvariable=self.connect_timeout_var).grid(row=13, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(settings_frame, text="读取时(秒):").grid(row=14, column=0, sticky="w", padx=5, pady=5)
        self.read_timeout_var = tk.IntVar(value=CRAWL_SETTINGS['timeout'][1])
        ttk.Spinbox(settings_frame, from_=1, to=120, width=5, textvariable=self.read_timeout_var).grid(row=14, column=1, sticky="w", padx=5, pady=5)
        
        # 分布式设置
        ttk.Label(settings_frame, text="--- 分布式设置 ---").grid(row=15, column=0, columnspan=2, pady=10, sticky="ew")
        
        # 13. 使用分布式
        self.distributed_var = tk.BooleanVar(value=CRAWL_SETTINGS['use_distributed'])
        ttk.Checkbutton(settings_frame, text="启用分布式模式", variable=self.distributed_var).grid(row=16, column=0, sticky="w", padx=5, pady=5)
        
        # 14. Redis主机
        ttk.Label(settings_frame, text="Redis主机:").grid(row=17, column=0, sticky="w", padx=5, pady=5)
        self.redis_host_var = tk.StringVar(value=CRAWL_SETTINGS['redis_host'])
        ttk.Entry(settings_frame, textvariable=self.redis_host_var, width=15).grid(row=17, column=1, sticky="w", padx=5, pady=5)
        
        # 15. Redis端口
        ttk.Label(settings_frame, text="Redis端口:").grid(row=18, column=0, sticky="w", padx=5, pady=5)
        self.redis_port_var = tk.IntVar(value=CRAWL_SETTINGS['redis_port'])
        ttk.Spinbox(settings_frame, from_=1, to=65535, width=5, textvariable=self.redis_port_var).grid(row=18, column=1, sticky="w", padx=5, pady=5)
        
        # 16. Redis密码
        ttk.Label(settings_frame, text="Redis密码:").grid(row=19, column=0, sticky="w", padx=5, pady=5)
        self.redis_password_var = tk.StringVar(value=CRAWL_SETTINGS['redis_password'])
        ttk.Entry(settings_frame, textvariable=self.redis_password_var, width=15, show="*").grid(row=19, column=1, sticky="w", padx=5, pady=5)
        
        # 17. 使用Bloom Filter
        self.bloom_filter_var = tk.BooleanVar(value=CRAWL_SETTINGS['use_bloom_filter'])
        ttk.Checkbutton(settings_frame, text="使用Bloom Filter去重", variable=self.bloom_filter_var).grid(row=20, column=0, sticky="w", padx=5, pady=5)
        
        # 高级功能
        ttk.Label(settings_frame, text="--- 高级功能 ---").grid(row=21, column=0, columnspan=2, pady=10, sticky="ew")
        
        # 18. 行为模拟
        self.behavior_sim_var = tk.BooleanVar(value=CRAWL_SETTINGS['behavior_simulation'])
        ttk.Checkbutton(settings_frame, text="模拟人类行为", variable=self.behavior_sim_var).grid(row=22, column=0, sticky="w", padx=5, pady=5)
        
        # 19. TLS指纹伪造
        self.tls_fingerprint_var = tk.BooleanVar(value=CRAWL_SETTINGS['tls_fingerprint'])
        ttk.Checkbutton(settings_frame, text="伪造TLS指纹", variable=self.tls_fingerprint_var).grid(row=23, column=0, sticky="w", padx=5, pady=5)
        
        # 20. AI内容提取
        self.ai_extraction_var = tk.BooleanVar(value=CRAWL_SETTINGS['ai_content_extraction'])
        ttk.Checkbutton(settings_frame, text="AI内容提取", variable=self.ai_extraction_var).grid(row=24, column=0, sticky="w", padx=5, pady=5)
        
        # 21. 异常检测
        self.anomaly_detection_var = tk.BooleanVar(value=CRAWL_SETTINGS['anomaly_detection'])
        ttk.Checkbutton(settings_frame, text="内容异常检测", variable=self.anomaly_detection_var).grid(row=25, column=0, sticky="w", padx=5, pady=5)
        
        # 按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="保存设置", command=self.save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="加载默认设置", command=self.load_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="保存到文件", command=self.save_to_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="从文件加载", command=self.load_from_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="测试代理", command=self.test_proxies).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=self.parent.destroy).pack(side=tk.RIGHT, padx=5)
    
    def save_settings(self):
        try:
            # 更新全局设置
            CRAWL_SETTINGS['retry_times'] = self.retry_var.get()
            CRAWL_SETTINGS['use_proxy'] = self.use_proxy_var.get()
            
            # 处理代理列表
            proxy_text = self.proxy_text.get(1.0, tk.END).strip()
            proxy_list = [p.strip() for p in proxy_text.split('\n') if p.strip()]
            CRAWL_SETTINGS['proxy_list'] = proxy_list
            CRAWL_SETTINGS['current_proxy_index'] = 0
            
            CRAWL_SETTINGS['ignore_ssl'] = self.ignore_ssl_var.get()
            CRAWL_SETTINGS['dynamic_rendering'] = self.dynamic_rendering_var.get()
            CRAWL_SETTINGS['request_delay'] = self.delay_var.get()
            CRAWL_SETTINGS['max_depth'] = self.depth_var.get()
            CRAWL_SETTINGS['image_crawling'] = self.image_crawling_var.get()
            CRAWL_SETTINGS['max_threads'] = self.threads_var.get()
            CRAWL_SETTINGS['image_size_limit'] = self.size_var.get()
            CRAWL_SETTINGS['text_crawling'] = self.text_crawling_var.get()
            CRAWL_SETTINGS['use_cloudscraper'] = self.cloudscraper_var.get()
            CRAWL_SETTINGS['timeout'] = (self.connect_timeout_var.get(), self.read_timeout_var.get())
            
            # 分布式设置
            CRAWL_SETTINGS['use_distributed'] = self.distributed_var.get()
            CRAWL_SETTINGS['redis_host'] = self.redis_host_var.get()
            CRAWL_SETTINGS['redis_port'] = self.redis_port_var.get()
            CRAWL_SETTINGS['redis_password'] = self.redis_password_var.get()
            CRAWL_SETTINGS['use_bloom_filter'] = self.bloom_filter_var.get()
            
            # 高级功能
            CRAWL_SETTINGS['behavior_simulation'] = self.behavior_sim_var.get()
            CRAWL_SETTINGS['tls_fingerprint'] = self.tls_fingerprint_var.get()
            CRAWL_SETTINGS['ai_content_extraction'] = self.ai_extraction_var.get()
            CRAWL_SETTINGS['anomaly_detection'] = self.anomaly_detection_var.get()
            
            self.log_callback("设置已保存")
            messagebox.showinfo("成功", "设置已成功保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存设置失败: {str(e)}")
    
    def test_proxies(self):
        proxy_text = self.proxy_text.get(1.0, tk.END).strip()
        proxy_list = [p.strip() for p in proxy_text.split('\n') if p.strip()]
        
        if not proxy_list:
            messagebox.showinfo("测试结果", "没有可测试的代理")
            return
        
        working_proxies = []
        failed_proxies = []
        
        for proxy in proxy_list:
            if test_proxy(proxy):
                working_proxies.append(proxy)
            else:
                failed_proxies.append(proxy)
        
        result = "代理测试结果:\n\n"
        result += f"可用代理 ({len(working_proxies)}个):\n"
        result += "\n".join(working_proxies) + "\n\n"
        result += f"不可用代理 ({len(failed_proxies)}个):\n"
        result += "\n".join(failed_proxies)
        
        messagebox.showinfo("代理测试结果", result)
    
    def load_default(self):
        default_settings = {
            'retry_times': 3,
            'use_proxy': False,
            'proxy_list': [],
            'current_proxy_index': 0,
            'ignore_ssl': False,
            'dynamic_rendering': False,
            'request_delay': 0.5,
            'max_depth': 1,
            'image_crawling': True,
            'max_threads': 5,
            'image_size_limit': 10,
            'text_crawling': True,
            'use_cloudscraper': False,
            'timeout': (10, 30),
            'redis_host': 'localhost',
            'redis_port': 6379,
            'redis_db': 0,
            'redis_password': '',
            'use_distributed': False,
            'use_bloom_filter': True,
            'behavior_simulation': True,
            'tls_fingerprint': True,
            'ai_content_extraction': True,
            'anomaly_detection': True,
        }
        
        CRAWL_SETTINGS.update(default_settings)
        
        # 更新UI控件
        self.retry_var.set(CRAWL_SETTINGS['retry_times'])
        self.use_proxy_var.set(CRAWL_SETTINGS['use_proxy'])
        self.proxy_text.delete(1.0, tk.END)
        self.proxy_text.insert(tk.END, "\n".join(CRAWL_SETTINGS['proxy_list']))
        self.ignore_ssl_var.set(CRAWL_SETTINGS['ignore_ssl'])
        self.dynamic_rendering_var.set(CRAWL_SETTINGS['dynamic_rendering'])
        self.delay_var.set(CRAWL_SETTINGS['request_delay'])
        self.depth_var.set(CRAWL_SETTINGS['max_depth'])
        self.image_crawling_var.set(CRAWL_SETTINGS['image_crawling'])
        self.threads_var.set(CRAWL_SETTINGS['max_threads'])
        self.size_var.set(CRAWL_SETTINGS['image_size_limit'])
        self.text_crawling_var.set(CRAWL_SETTINGS['text_crawling'])
        self.cloudscraper_var.set(CRAWL_SETTINGS['use_cloudscraper'])
        self.connect_timeout_var.set(CRAWL_SETTINGS['timeout'][0])
        self.read_timeout_var.set(CRAWL_SETTINGS['timeout'][1])
        self.distributed_var.set(CRAWL_SETTINGS['use_distributed'])
        self.redis_host_var.set(CRAWL_SETTINGS['redis_host'])
        self.redis_port_var.set(CRAWL_SETTINGS['redis_port'])
        self.redis_password_var.set(CRAWL_SETTINGS['redis_password'])
        self.bloom_filter_var.set(CRAWL_SETTINGS['use_bloom_filter'])
        self.behavior_sim_var.set(CRAWL_SETTINGS['behavior_simulation'])
        self.tls_fingerprint_var.set(CRAWL_SETTINGS['tls_fingerprint'])
        self.ai_extraction_var.set(CRAWL_SETTINGS['ai_content_extraction'])
        self.anomaly_detection_var.set(CRAWL_SETTINGS['anomaly_detection'])
        
        self.log_callback("已加载默认设置")
        messagebox.showinfo("成功", "已加载默认设置")
    
    def save_to_file(self):
        try:
            with open('crawler_config.json', 'w') as f:
                json.dump(CRAWL_SETTINGS, f, indent=4)
            self.log_callback("配置已保存到 crawler_config.json")
            messagebox.showinfo("成功", "配置已成功保存到文件")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")
    
    def load_from_file(self):
        try:
            with open('crawler_config.json', 'r') as f:
                settings = json.load(f)
            
            # 更新全局设置
            CRAWL_SETTINGS.update(settings)
            
            # 更新UI控件
            self.retry_var.set(CRAWL_SETTINGS['retry_times'])
            self.use_proxy_var.set(CRAWL_SETTINGS['use_proxy'])
            self.proxy_text.delete(1.0, tk.END)
            self.proxy_text.insert(tk.END, "\n".join(CRAWL_SETTINGS['proxy_list']))
            self.ignore_ssl_var.set(CRAWL_SETTINGS['ignore_ssl'])
            self.dynamic_rendering_var.set(CRAWL_SETTINGS['dynamic_rendering'])
            self.delay_var.set(CRAWL_SETTINGS['request_delay'])
            self.depth_var.set(CRAWL_SETTINGS['max_depth'])
            self.image_crawling_var.set(CRAWL_SETTINGS['image_crawling'])
            self.threads_var.set(CRAWL_SETTINGS['max_threads'])
            self.size_var.set(CRAWL_SETTINGS['image_size_limit'])
            self.text_crawling_var.set(CRAWL_SETTINGS['text_crawling'])
            self.cloudscraper_var.set(CRAWL_SETTINGS['use_cloudscraper'])
            self.connect_timeout_var.set(CRAWL_SETTINGS['timeout'][0])
            self.read_timeout_var.set(CRAWL_SETTINGS['timeout'][1])
            self.distributed_var.set(CRAWL_SETTINGS['use_distributed'])
            self.redis_host_var.set(CRAWL_SETTINGS['redis_host'])
            self.redis_port_var.set(CRAWL_SETTINGS['redis_port'])
            self.redis_password_var.set(CRAWL_SETTINGS['redis_password'])
            self.bloom_filter_var.set(CRAWL_SETTINGS['use_bloom_filter'])
            self.behavior_sim_var.set(CRAWL_SETTINGS['behavior_simulation'])
            self.tls_fingerprint_var.set(CRAWL_SETTINGS['tls_fingerprint'])
            self.ai_extraction_var.set(CRAWL_SETTINGS['ai_content_extraction'])
            self.anomaly_detection_var.set(CRAWL_SETTINGS['anomaly_detection'])
            
            self.log_callback("配置已从文件加载")
            messagebox.showinfo("成功", "配置已成功加载")
        except FileNotFoundError:
            messagebox.showwarning("警告", "配置文件不存在")
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败: {str(e)}")

# 主程序入口
if __name__ == "__main__":
    root = tk.Tk()
    app = CrawlerGUI(root)
    root.mainloop()
