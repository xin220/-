#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import requests
from bs4 import BeautifulSoup
import urllib.parse as urlparse
from urllib.robotparser import RobotFileParser

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
    """获取网页内容并提取所有文本"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding
        
        if response.status_code != 200:
            return None, f"错误: HTTP状态码 {response.status_code}"
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 移除不需要的元素
        for element in soup(['script', 'style', 'noscript', 'meta', 'link', 'header', 'footer']):
            element.decompose()
        
        # 提取所有文本
        text = soup.get_text(separator='\n', strip=True)
        cleaned_text = re.sub(r'\n{3,}', '\n\n', text)  # 减少过多换行
        
        return cleaned_text, None
    
    except Exception as e:
        return None, f"抓取失败: {str(e)}"

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

def main():
    clear_screen()
    print("""
███████╗██████╗ ███████╗ ██████╗ █████╗ ███████╗
██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗██╔════╝
█████╗  ██████╔╝███████╗██║     ███████║███████╗
██╔══╝  ██╔══██╗╚════██║██║     ██╔══██║╚════██║
███████╗██║  ██║███████║╚██████╗██║  ██║███████║
╚══════╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚══════╝
命令行网页爬虫 v1.0 · 输入数字进行操作
==============================================""")

    current_url = None
    web_content = None

    while True:
        main_menu = [
            "输入网址抓取内容",
            "预览抓取的文本",
            "保存到文件",
            "设置请求参数（高级）",
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
            print("\n高级功能开发中...")
            print("未来版本将支持设置请求头、代理等功能")
            input("\n按Enter返回主菜单...")
            
        elif choice == '5':
            current_url = None
            web_content = None
            print("\n数据已重置!")
            input("按Enter继续...")
            
        else:
            print("\n无效输入！请选择1-5")
            
        clear_screen()
        print(f"\n当前状态: {f'已加载 {urlparse.urlparse(current_url).netloc}' if current_url else '未加载网页'}")

if __name__ == "__main__":
    main()
