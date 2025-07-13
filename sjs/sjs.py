import os
import requests
from PIL import Image, ImageFilter
from io import BytesIO
import base64
import time
import random
import re
from bs4 import BeautifulSoup
import json
import sys
import xml.etree.ElementTree as ET
import http.client  # 调试用

# 调试模式开关
DEBUG_MODE = False  # 设置为True启用请求日志

# 所需依赖 requests pillow

# 从环境变量获取配置
ACCOUNTS = os.environ.get('XSJ_ACCOUNTS', '')  # 多账户配置
OCR_SERVICE = os.environ.get('OCR_SERVICE', '')
main_url = "https://xsijishe.com"
TIMEOUT = 15  # 延长超时时间
MAX_RETRY = 3
COOLDOWN = {7: 300, 3: 600, 1: 1800}  # 剩余次数对应的冷却时间（秒）

# 调试设置
if DEBUG_MODE:
    http.client.HTTPConnection.debuglevel = 1
    import logging
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

# 登录用到的参数
sign_url = '/k_misign-sign.html'

def parse_accounts(accounts_str):
    """解析多账户配置（保持不变）"""
    # ...（原有实现不变）...

def get_random_user_agent():
    """生成随机User-Agent（保持不变）"""
    # ...（原有实现不变）...

def get_session_headers():
    """获取增强的会话请求头"""
    return {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": main_url + "/",
        "Origin": main_url,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest"
    }

def preprocess_image(img):
    """增强的验证码预处理"""
    # 转换为灰度图
    img = img.convert('L')
    
    # 二值化处理
    threshold = 128
    img = img.point(lambda p: 255 if p > threshold else 0)
    
    # 去噪处理
    img = img.filter(ImageFilter.MedianFilter(size=3))
    
    # 边缘增强
    img = img.filter(ImageFilter.EDGE_ENHANCE)
    
    return img

def recognize_captcha(base64_img):
    """改进的验证码识别"""
    try:
        # 提取图像数据
        if "," in base64_img:
            header, data = base64_img.split(",", 1)
        else:
            data = base64_img
        
        # 解码图像
        img_data = base64.b64decode(data)
        img = Image.open(BytesIO(img_data))
        
        # 图像预处理
        img = preprocess_image(img)
        
        # 转换为PNG格式
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        processed_data = base64.b64encode(buffer.getvalue()).decode()
        
        # 发送OCR请求
        resp = requests.post(
            OCR_SERVICE,
            json={
                "image": f"data:image/png;base64,{processed_data}",
                "options": {"length": 4}  # 强制4位验证码
            },
            timeout=TIMEOUT
        )
        
        if resp.ok:
            result = resp.json().get("result", "").strip().lower()
            # 过滤非法字符
            result = re.sub(r"[^a-z0-9]", "", result)[:4]
            return result.ljust(4, "0")  # 补足4位
        return ""
    except Exception as e:
        print(f"🤖 OCR识别错误: {e}")
        return ""

def get_form_info(session):
    """增强的表单信息获取"""
    for _ in range(MAX_RETRY):
        try:
            login_page_url = f"{main_url}/member.php?mod=logging&action=login"
            r = session.get(login_page_url, timeout=TIMEOUT)
            r.raise_for_status()
            
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # 获取关键参数
            formhash = soup.find('input', {'name': 'formhash'}).get('value', '')
            loginhash = soup.find('input', {'name': 'loginhash'}).get('value', '')
            referer = soup.find('input', {'name': 'referer'}).get('value', main_url)
            
            # 动态获取seccodehash
            sec_element = soup.find('div', id=re.compile(r'^seccode_'))
            if sec_element:
                seccodehash = sec_element['id'].replace('seccode_', '')
            else:
                # 从验证码图片URL提取
                captcha_img = soup.find('img', id=re.compile(r'^sec'))
                if captcha_img:
                    src = captcha_img.get('src', '')
                    seccodehash = re.search(r'idhash=([a-zA-Z0-9]+)', src).group(1)
                else:
                    seccodehash = ''
            
            return formhash, loginhash, seccodehash, referer
        except Exception as e:
            print(f"⚠️ 获取登录参数失败: {e}")
            time.sleep(2)
    return None, None, None, None

def check_captcha(session, seccodehash, seccodeverify):
    """精确的验证码校验"""
    check_url = f"{main_url}/misc.php"
    params = {
        "mod": "seccode",
        "action": "check",
        "inajax": 1,
        "idhash": seccodehash,
        "secverify": seccodeverify
    }
    
    try:
        r = session.get(check_url, params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            return False
        
        # 解析XML响应
        root = ET.fromstring(r.text)
        if root.find('.//cdata') is not None:
            cdata = root.find('.//cdata').text.lower()
            return 'succeed' in cdata
        return False
    except ET.ParseError:
        return 'succeed' in r.text.lower()
    except Exception as e:
        print(f"❌ 验证码校验异常: {e}")
        return False

def handle_login_errors(error_text):
    """处理登录错误和冷却机制"""
    # 检测剩余尝试次数
    match = re.search(r'还可以尝试 (\d+) 次', error_text)
    if match:
        remaining = int(match.group(1))
        for threshold in sorted(COOLDOWN.keys(), reverse=True):
            if remaining <= threshold:
                print(f"⚠️ 触发冷却机制，等待 {COOLDOWN[threshold]}秒")
                time.sleep(COOLDOWN[threshold])
                return True
    return False

def login_account(username, password):
    """增强的登录流程"""
    session = requests.Session()
    session.headers.update(get_session_headers())
    
    print(f"\n🔐 开始登录账户: {username}")
    
    for attempt in range(1, MAX_RETRY + 1):
        print(f"⏳ 尝试 #{attempt}")
        
        # 获取登录参数
        formhash, loginhash, seccodehash, referer = get_form_info(session)
        if not all([formhash, seccodehash]):
            continue
            
        # 获取验证码
        captcha_url = f"{main_url}/misc.php?mod=seccode&update={int(time.time())}&idhash={seccodehash}"
        try:
            captcha_resp = session.get(captcha_url, timeout=TIMEOUT)
            if "image" not in captcha_resp.headers.get("Content-Type", ""):
                print(f"❗ 验证码响应异常（{captcha_resp.status_code}）")
                continue
        except Exception as e:
            print(f"❌ 获取验证码失败: {e}")
            continue
        
        # 识别验证码
        img = Image.open(BytesIO(captcha_resp.content))
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        base64_img = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
        
        seccodeverify = recognize_captcha(base64_img)
        if len(seccodeverify) != 4:
            print(f"🤖 验证码识别失败: {seccodeverify}")
            continue
        
        # 校验验证码
        if not check_captcha(session, seccodehash, seccodeverify):
            print(f"❌ 验证码校验失败: {seccodeverify}")
            continue
        
        print(f"✅ 验证码校验成功: {seccodeverify}")
        
        # 构建登录请求
        login_url = f"{main_url}/member.php?mod=logging&action=login"
        payload = {
            "formhash": formhash,
            "loginhash": loginhash,
            "referer": referer,
            "username": username,
            "password": password,
            "seccodehash": seccodehash,
            "seccodemodid": "member::logging",
            "seccodeverify": seccodeverify,
            "loginsubmit": "true"
        }
        
        try:
            r = session.post(login_url, data=payload, timeout=20)
            if DEBUG_MODE:
                print(f"登录响应状态码: {r.status_code}")
                print(f"响应内容: {r.text[:500]}...")
            
            # 处理登录结果
            if "欢迎您回来" in r.text or "login_succeed" in r.url:
                # 验证会话状态
                profile_url = f"{main_url}/home.php?mod=space"
                profile_resp = session.get(profile_url, timeout=TIMEOUT)
                if username in profile_resp.text:
                    print(f"🎉 账户 {username} 登录成功！")
                    return session
                else:
                    print("❌ 会话验证失败")
                    continue
            else:
                # 解析错误信息
                error_msg = ""
                if "ajax_login" in r.text:
                    soup = BeautifulSoup(r.text, 'html.parser')
                    error_div = soup.find('div', class_='alert_error')
                    error_msg = error_div.get_text(strip=True) if error_div else "未知错误"
                
                # 处理账户锁定
                if handle_login_errors(error_msg):
                    continue
                
                print(f"❌ 登录失败: {error_msg}")
        except Exception as e:
            print(f"❌ 登录请求异常: {e}")
        
        time.sleep(random.uniform(1, 3))
    
    print(f"❌ 账户 {username} 登录失败，达到最大重试次数")
    return None

# 后续的 do_sign_in 和 get_user_info 函数保持不变（但建议添加重试机制）
# ...（原有实现保持不变，可添加重试逻辑）...

if __name__ == "__main__":
    # ...（主流程保持不变）...
