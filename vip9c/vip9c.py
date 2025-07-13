import requests
import os
import hashlib

# 从青龙环境变量获取账户列表
ACCOUNTS = os.getenv('9VIP_ACCOUNTS', '')
if not ACCOUNTS:
    print("⚠️ 未检测到环境变量9VIP_ACCOUNTS，请添加你的账户信息")
    exit(1)

# 解析账户信息
account_list = []
for account in ACCOUNTS.split('&'):
    if ',' in account:
        username, password = account.split(',', 1)
        account_list.append((username.strip(), password.strip()))

if not account_list:
    print("⚠️ 未检测到有效的账户信息")
    exit(1)

# 基础配置
LOGIN_URL = "https://vipc9.com/wp-admin/admin-ajax.php"
SIGN_URL = LOGIN_URL
COOKIE_DIR = "./9vip_cookies"
HEADERS_BASE = {
    "Origin": "https://vipc9.com",
    "Referer": "https://vipc9.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9"
}

# 创建cookie目录
if not os.path.exists(COOKIE_DIR):
    os.makedirs(COOKIE_DIR)


def get_cookie_file(username):
    """生成基于用户名的cookie文件名"""
    username_hash = hashlib.md5(username.encode()).hexdigest()
    return os.path.join(COOKIE_DIR, f"{username_hash}.txt")


def save_cookie(username, cookie_str):
    """保存cookie到文件"""
    cookie_file = get_cookie_file(username)
    with open(cookie_file, 'w') as f:
        f.write(cookie_str)


def load_cookie(username):
    """从文件加载cookie"""
    cookie_file = get_cookie_file(username)
    if os.path.exists(cookie_file):
        with open(cookie_file, 'r') as f:
            return f.read().strip()
    return ""


def cookie_str_to_dict(cookie_str):
    """将cookie字符串转换为字典"""
    cookies = {}
    for item in cookie_str.split(';'):
        if '=' in item:
            k, v = item.strip().split('=', 1)
            cookies[k] = v
    return cookies


def login(username, password):
    """执行登录操作"""
    print(f"🔐 用户 {username} 尝试登录中...")
    data = {
        "action": "user_login",
        "username": username,
        "password": password
    }

    session = requests.Session()
    try:
        resp = session.post(LOGIN_URL, headers=HEADERS_BASE, data=data, timeout=10)
        result = resp.json()
    except Exception as e:
        print(f"❌ 登录请求异常: {str(e)}")
        return None

    if result.get("status") == "1":
        print(f"✅ 用户 {username} 登录成功，保存 Cookie")
        cookie_str = "; ".join([f"{c.name}={c.value}" for c in session.cookies])
        save_cookie(username, cookie_str)
        return session.cookies
    else:
        print(f"❌ 用户 {username} 登录失败：{result.get('msg', '未知错误')}")
        return None


def sign_in(username, cookies_dict):
    """执行签到操作"""
    print(f"📩 用户 {username} 尝试签到中...")
    data = {"action": "user_qiandao"}
    
    try:
        resp = requests.post(SIGN_URL, headers=HEADERS_BASE, cookies=cookies_dict, data=data, timeout=10)
        result = resp.json()
    except Exception as e:
        print(f"❌ 签到请求异常: {str(e)}")
        return False

    if result.get("status") == "1":
        print(f"🎉 用户 {username} 签到成功：{result.get('msg')}")
        return True
    elif "请登录" in result.get("msg", ""):
        print(f"⚠️ 用户 {username} 的 Cookie 已失效")
        return False
    else:
        print(f"⚠️ 用户 {username} 签到失败：{result.get('msg')}")
        return True  # 不是因为未登录的失败


def process_account(username, password):
    """处理单个账户的签到流程"""
    cookie_str = load_cookie(username)
    cookies_dict = cookie_str_to_dict(cookie_str)
    
    # 尝试使用现有cookie签到
    if cookies_dict:
        if sign_in(username, cookies_dict):
            return
    
    # 登录并重新尝试签到
    new_cookies = login(username, password)
    if new_cookies:
        cookies_dict = requests.utils.dict_from_cookiejar(new_cookies)
        sign_in(username, cookies_dict)


if __name__ == "__main__":
    print(f"🌟 9VIP 多账户签到脚本开始，共 {len(account_list)} 个账户 🌟")
    
    for idx, (username, password) in enumerate(account_list, 1):
        print(f"\n🔰 处理账户 {idx}/{len(account_list)}: {username}")
        process_account(username, password)
        
        # 账户间延迟
        if idx < len(account_list):
            print("\n⏳ 等待3秒处理下一个账户...")
            time.sleep(3)
    
    print("\n✨ 所有账户处理完成！")
