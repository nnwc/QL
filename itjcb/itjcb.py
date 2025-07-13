import time
import re
import base64
import random
from io import BytesIO
import os

import requests
from bs4 import BeautifulSoup
from PIL import Image
import numpy as np

#需要安装的依赖 requests beautifulsoup4 pillow numpy

# 从环境变量获取配置
ACCOUNTS = os.environ.get('ITJC8_ACCOUNTS', '')  # 多账户配置
OCR_SERVICE = os.environ.get('OCR_SERVICE', '')  # OCR服务地址

# 检查环境变量是否设置
if not ACCOUNTS or not OCR_SERVICE:
    print("❌ 错误：请设置环境变量 ITJC8_ACCOUNTS 和 OCR_SERVICE")
    exit(1)

LOGIN_PAGE_URL = "https://www.itjc8.com/member.php?mod=logging&action=login"
LOGIN_POST_URL = "https://www.itjc8.com/member.php?mod=logging&action=login&loginsubmit=yes&inajax=1"
SIGN_URL = "https://www.itjc8.com/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&sign_as=1&inajax=1"

COOKIE_FILE_PREFIX = "./itlt_"  # cookie文件前缀
qdxq_list = ["kx", "ng", "ym", "wl", "nu", "ch", "fd", "yl", "shuai"]
MAX_RETRY = 3

# 随机User-Agent列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
]

def get_random_headers():
    """生成随机请求头"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.itjc8.com/"
    }

def parse_accounts(accounts_str):
    """解析多账户配置"""
    accounts = []
    
    # 替换所有分隔符为统一的分隔符
    normalized_str = accounts_str.replace("@", "&").replace("\n", "&")
    
    # 分割账户
    account_list = [acc.strip() for acc in normalized_str.split("&") if acc.strip()]
    
    for account_str in account_list:
        if not account_str:
            continue
            
        # 分割账户信息
        parts = account_str.split(":", 1)
        
        if len(parts) < 2:
            print(f"❌ 账户信息不完整: {account_str}")
            continue
            
        username = parts[0].strip()
        password = parts[1].strip()
        
        accounts.append({
            "username": username,
            "password": password
        })
    
    return accounts

def parse_login_params(html):
    soup = BeautifulSoup(html, 'html.parser')

    formhash_tag = soup.find('input', {'name': 'formhash'})
    formhash = formhash_tag['value'] if formhash_tag else None

    login_form = soup.find('form', id=re.compile(r'^loginform_'))
    loginhash = None
    if login_form:
        id_attr = login_form.get('id', '')
        match = re.search(r'loginform_(\w+)', id_attr)
        if match:
            loginhash = match.group(1)
        else:
            action = login_form.get('action', '')
            match = re.search(r'loginhash=(\w+)', action)
            if match:
                loginhash = match.group(1)

    seccodehash_tag = soup.find('input', {'name': 'seccodehash'})
    seccodehash = seccodehash_tag['value'] if seccodehash_tag else None

    seccodemodid_tag = soup.find('input', {'name': 'seccodemodid'})
    seccodemodid = seccodemodid_tag['value'] if seccodemodid_tag else None

    captcha_idhash = None
    for img in soup.find_all('img'):
        src = img.get('src', '')
        match = re.search(r'idhash=(\w+)', src)
        if match:
            captcha_idhash = match.group(1)
            break

    return formhash, loginhash, seccodehash, seccodemodid, captcha_idhash

def fetch_captcha_frames(session, captcha_idhash):
    url = f"https://www.itjc8.com/misc.php?mod=seccode&idhash={captcha_idhash}&update={random.randint(100000, 999999)}"
    try:
        resp = session.get(url, headers=get_random_headers(), timeout=15)
        resp.raise_for_status()
        gif = Image.open(BytesIO(resp.content))
        frames = []
        for i in range(gif.n_frames):
            gif.seek(i)
            frame = gif.convert("RGB")
            buf = BytesIO()
            frame.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            frames.append({"frame_index": i, "base64_data": b64})
        return frames
    except Exception as e:
        print(f"获取验证码帧失败: {e}")
        return []

def get_image_sharpness(b64):
    try:
        import cv2
        img = Image.open(BytesIO(base64.b64decode(b64))).convert('L')
        arr = np.array(img)
        return cv2.Laplacian(arr, cv2.CV_64F).var()
    except ImportError:
        return 0
    except Exception:
        return 0

def recognize_captcha(frames):
    valid = []
    for f in frames:
        sharpness = get_image_sharpness(f["base64_data"])
        try:
            r = requests.post(OCR_SERVICE, json={"image": f["base64_data"]}, timeout=15)
            r.raise_for_status()
            res_json = r.json()
            result = res_json.get("result", "").strip()
            confidence = res_json.get("confidence", 0)
            print(f"帧 {f['frame_index']} 识别: {result}, 置信度: {confidence}, 清晰度: {sharpness:.2f}")
            if len(result) == 4 and result.isalnum():
                valid.append({"result": result, "confidence": confidence, "sharpness": sharpness})
        except Exception as e:
            print(f"OCR失败: {e}")
    if not valid:
        return ""
    valid.sort(key=lambda x: (-x["confidence"], -x["sharpness"]))
    return valid[0]["result"]

def save_cookies(username, cookies):
    """保存cookie到文件"""
    cookie_file = f"{COOKIE_FILE_PREFIX}{username}.txt"
    try:
        cookie_str = "; ".join(f"{c.name}={c.value}" for c in cookies)
        with open(cookie_file, "w") as f:
            f.write(cookie_str)
        print(f"✅ Cookie 已保存: {cookie_file}")
    except Exception as e:
        print(f"Cookie保存失败: {e}")

def load_cookies(username):
    """从文件加载cookie"""
    cookie_file = f"{COOKIE_FILE_PREFIX}{username}.txt"
    if os.path.exists(cookie_file):
        try:
            with open(cookie_file, "r") as f:
                cookie_str = f.read().strip()
            cookies = {}
            for c in cookie_str.split("; "):
                if "=" in c:
                    k, v = c.split("=", 1)
                    cookies[k] = v
            print(f"✅ Cookie 已加载: {cookie_file}")
            return cookies
        except Exception as e:
            print(f"加载Cookie失败: {e}")
    return None

def login(username, password):
    session = requests.Session()
    session.headers.update(get_random_headers())
    
    for attempt in range(1, MAX_RETRY + 1):
        print(f"\n🔐 账户 {username} 第{attempt}次尝试登录...")
        
        try:
            # 获取登录页面
            r = session.get(LOGIN_PAGE_URL, timeout=15)
            r.raise_for_status()
            html = r.text
            
            formhash, loginhash, seccodehash, seccodemodid, captcha_idhash = parse_login_params(html)
            print(f"获取参数: formhash={formhash}, loginhash={loginhash}, seccodehash={seccodehash}, seccodemodid={seccodemodid}, captcha_idhash={captcha_idhash}")

            if not all([formhash, loginhash, seccodehash, seccodemodid, captcha_idhash]):
                print("动态参数不完整，重新尝试...")
                time.sleep(2)
                continue

            frames = fetch_captcha_frames(session, captcha_idhash)
            if not frames:
                print("无法获取验证码图片，重新尝试...")
                time.sleep(2)
                continue

            captcha = recognize_captcha(frames)
            if not captcha:
                print("验证码识别失败，重新尝试...")
                time.sleep(2)
                continue

            print(f"识别验证码: {captcha}")

            post_data = {
                "formhash": formhash,
                "referer": "https://www.itjc8.com/",
                "username": username,
                "password": password,
                "questionid": "0",
                "answer": "",
                "seccodehash": seccodehash,
                "seccodemodid": seccodemodid,
                "seccodeverify": captcha,
            }

            full_url = f"{LOGIN_POST_URL}&loginhash={loginhash}"
            r = session.post(full_url, data=post_data, timeout=20)
            r.raise_for_status()
            
            # 检查登录结果
            if any(s in r.text for s in ["欢迎您回来", "您已经登录", "登录成功"]):
                print("🎉 登录成功")
                save_cookies(username, session.cookies)
                return session
            else:
                print(f"登录失败，响应片段：{r.text[:300]}")
                
                # 尝试从响应中提取错误信息
                soup = BeautifulSoup(r.text, 'html.parser')
                if error_div := soup.find('div', class_='alert_error'):
                    error_msg = error_div.get_text(strip=True)
                    print(f"❌ 错误信息: {error_msg}")
                elif error_div := soup.find('div', class_='alert_info'):
                    error_msg = error_div.get_text(strip=True)
                    print(f"⚠️ 提示信息: {error_msg}")
                    
        except requests.exceptions.RequestException as e:
            print(f"网络请求异常: {e}")
        except Exception as e:
            print(f"登录过程异常: {e}")
        
        print("3秒后重试...")
        time.sleep(3)

    print("❌ 登录失败，达到最大重试次数")
    return None

def sign_in(username, password):
    # 先尝试从cookie签到
    print(f"\n🔄 账户 {username} 尝试签到...")
    
    # 加载cookie
    cookies = load_cookies(username)
    session = requests.Session()
    session.headers.update(get_random_headers())
    
    if cookies:
        # 设置cookie
        session.cookies.update(cookies)
        print("✅ 使用cookie进行签到")
    else:
        print("❌ Cookie文件不存在或加载失败")
        return False

    # 使用cookie尝试签到
    try:
        # 获取首页以获取formhash
        r = session.get("https://www.itjc8.com/", timeout=10)
        r.raise_for_status()
        
        # 检查登录状态
        if "退出" not in r.text:
            print("❌ Cookie失效，需要重新登录")
            return False
            
        soup = BeautifulSoup(r.text, "html.parser")
        formhash_tag = soup.find("input", {"name": "formhash"})
        formhash = formhash_tag['value'] if formhash_tag else None
        if not formhash:
            print("无法获取签到formhash")
            return False

        day_xq = random.choice(qdxq_list)

        post_data = {
            "formhash": formhash,
            "qdxq" : day_xq,
            "qdmode": "3",
            "todaysay": "",
            "fastreply": "0",
        }
        
        sign_resp = session.post(SIGN_URL, data=post_data, timeout=15)
        sign_resp.raise_for_status()

        text = sign_resp.text
        # 简单提取 <div class="c"> 内文字
        m = re.search(r'<div class="c">\s*(.*?)\s*</div>', text, re.S)
        msg = m.group(1).strip() if m else "未知签到返回"

        # 简单emoji美化
        if "成功" in msg or "已签到" in msg:
            print(f"✅ 签到成功: {msg} 🎉")
            return True
        elif "心情不正确" in msg:
            print(f"⚠️ 签到失败: {msg}")
            return False
        elif "未登录" in msg or "登录" in msg:
            print("❌ Cookie 失效或未登录，需要重新登录")
            return False
        else:
            print(f"ℹ️ 签到响应: {msg}")
            return True

    except Exception as e:
        print(f"签到异常: {e}")
        return False

def process_account(account):
    """处理单个账户"""
    username = account["username"]
    password = account["password"]
    
    # 尝试使用cookie签到
    success = sign_in(username, password)
    
    if not success:
        print(f"需要登录后签到")
        session = login(username, password)
        if session:
            print("登录成功，开始签到...")
            # 登录后立即尝试签到
            success = sign_in(username, password)
            if success:
                print(f"🎉 账户 {username} 签到完成")
            else:
                print(f"❌ 账户 {username} 签到失败")
        else:
            print(f"❌ 账户 {username} 登录失败，无法签到")
    else:
        print(f"🎉 账户 {username} 使用Cookie签到成功")
    
    return success

if __name__ == "__main__":
    # 解析多账户配置
    accounts = parse_accounts(ACCOUNTS)
    
    if not accounts:
        print("❌ 没有找到有效的账户配置")
        exit(1)
    
    print(f"🔍 找到 {len(accounts)} 个账户")
    
    # 处理每个账户
    success_count = 0
    for account in accounts:
        if process_account(account):
            success_count += 1
        print("\n" + "="*50 + "\n")  # 账户分隔线
    
    print(f"\n✅ 所有账户处理完成，成功: {success_count}/{len(accounts)}")
