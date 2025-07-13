import os
import requests
import re
import pickle
import time
from bs4 import BeautifulSoup
import json

# 从环境变量获取多账户配置
def get_accounts_from_env():
    """从环境变量解析多账户配置"""
    accounts = []
    
    # 从环境变量中获取配置
    accounts_str = os.getenv('RKLT_ACCOUNTS', '')
    if not accounts_str:
        print("❌ 错误：请设置环境变量 RKLT_ACCOUNTS")
        return accounts
    
    # 支持多种分隔符：@、&、换行符
    separator = "@" if "@" in accounts_str else "&" if "&" in accounts_str else "\n"
    
    # 分割账户
    account_list = [acc.strip() for acc in accounts_str.split(separator) if acc.strip()]
    
    for index, account in enumerate(account_list, 1):
        # 分割用户名和密码
        if ":" not in account:
            print(f"❌ 账户 {index}：格式无效，应为 '用户名:密码'")
            continue
            
        username, password = account.split(":", 1)
        username = username.strip()
        password = password.strip()
        
        if not username or not password:
            print(f"❌ 账户 {index}：用户名或密码为空")
            continue
        
        accounts.append({
            "username": username,
            "password": password,
            "id": index
        })
    
    return accounts

# 为每个账户创建独立的Cookie文件
def get_cookie_file(username):
    """生成账户特定的Cookie文件名"""
    safe_username = re.sub(r'[^a-zA-Z0-9]', '_', username)
    return f"./rklt_cookie_{safe_username}.pkl"

def save_cookies(session, username):
    """保存Cookie到文件"""
    cookie_file = get_cookie_file(username)
    try:
        with open(cookie_file, 'wb') as f:
            pickle.dump(session.cookies, f)
        return True
    except Exception as e:
        print(f"❌ 保存Cookie失败: {e}")
        return False

def load_cookies(session, username):
    """从文件加载Cookie"""
    cookie_file = get_cookie_file(username)
    if os.path.exists(cookie_file):
        try:
            with open(cookie_file, 'rb') as f:
                session.cookies.update(pickle.load(f))
            return True
        except Exception as e:
            print(f"❌ 加载Cookie失败: {e}")
    return False

def get_formhash(session):
    url = "https://www.ruike1.com/"
    try:
        resp = session.get(url)
        resp.encoding = "gbk"
        match = re.search(r'name="formhash" value="([a-f0-9]{8})"', resp.text)
        if match:
            return match.group(1)
        else:
            print("❌ 无法提取 formhash")
            return None
    except Exception as e:
        print(f"❌ 获取 formhash 出错: {e}")
        return None

def login(username, password):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    
    formhash = get_formhash(session)
    if not formhash:
        return None

    url = "https://www.ruike1.com/member.php?mod=logging&action=login&loginsubmit=yes&infloat=yes&lssubmit=yes&inajax=1"
    headers = {
        "Host": "www.ruike1.com",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.ruike1.com",
        "Referer": "https://www.ruike1.com/",
    }
    data = {
        "fastloginfield": "username",
        "username": username,
        "password": password,
        "cookietime": "2592000",
        "formhash": formhash,
        "quickforward": "yes",
        "handlekey": "ls"
    }
    
    try:
        response = session.post(url, headers=headers, data=data)
        response.encoding = "gbk"

        if response.status_code == 200:
            if "window.location.href" in response.text:
                print("✅ 登录成功")
                save_cookies(session, username)
                return session
            else:
                # 尝试提取错误信息
                error_match = re.search(r'<div class="c">([^<]+)</div>', response.text)
                if error_match:
                    print(f"❌ 登录失败: {error_match.group(1)}")
                else:
                    print("❌ 登录失败，可能用户名或密码错误")
        else:
            print(f"❌ 登录请求失败，状态码：{response.status_code}")
    except Exception as e:
        print(f"❌ 登录请求异常: {e}")
    
    return None

def sign_in(session):
    formhash = get_formhash(session)
    if not formhash:
        return False

    url = f"https://www.ruike1.com/k_misign-sign.html?operation=qiandao&format=global_usernav_extra&formhash={formhash}&inajax=1&ajaxtarget=k_misign_topb"
    headers = {
        "Host": "www.ruike1.com",
        "Referer": "https://www.ruike1.com/",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    try:
        response = session.get(url, headers=headers)
        response.encoding = "gbk"
        
        if response.status_code == 200:
            if "今日已签" in response.text:
                print("✅ 今日已签到")
                return True
            elif "签到成功" in response.text or "已成功签到" in response.text:
                print("🎉 签到成功！")
                return True
            else:
                # 尝试提取错误信息
                error_match = re.search(r'<div class="c">([^<]+)</div>', response.text)
                if error_match:
                    print(f"⚠️ 签到失败: {error_match.group(1)}")
                else:
                    print(f"⚠️ 无法确认签到状态: {response.text[:100]}...")
        else:
            print(f"❌ 签到失败，HTTP 状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 签到请求异常：{e}")
    
    return False

def get_credit(session):
    url = "https://www.ruike1.com/"
    try:
        response = session.get(url)
        response.encoding = "gbk"

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            credit_tag = soup.find("a", id="extcreditmenu")
            if credit_tag:
                credit_text = credit_tag.text.strip()
                match = re.search(r"积分[:：]\s*(\d+)", credit_text)
                if match:
                    credit = int(match.group(1))
                    print(f"💰 当前积分: {credit}")
                    return credit
                else:
                    print(f"⚠️ 未能提取积分: {credit_text}")
            else:
                print("❌ 未找到积分信息")
        else:
            print(f"❌ 获取积分失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 获取积分出错: {e}")
    
    return None

def process_account(account):
    """处理单个账户"""
    username = account["username"]
    password = account["password"]
    account_id = account["id"]
    
    print(f"\n{'='*50}")
    print(f"🚀 处理账户 #{account_id}: {username}")
    print(f"{'='*50}")
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    
    # 尝试使用Cookie登录
    if load_cookies(session, username):
        print("📦 使用保存的Cookie")
        if sign_in(session):
            get_credit(session)
            return True
        else:
            print("🔁 Cookie可能失效，尝试重新登录")
    
    # 使用用户名密码登录
    logged_in_session = login(username, password)
    if logged_in_session:
        if sign_in(logged_in_session):
            get_credit(logged_in_session)
            return True
    
    return False

if __name__ == "__main__":
    # 获取多账户配置
    accounts = get_accounts_from_env()
    
    if not accounts:
        print("❌ 没有有效的账户配置，脚本终止")
        exit(1)
    
    print(f"🔍 找到 {len(accounts)} 个账户")
    
    # 处理每个账户
    success_count = 0
    for account in accounts:
        if process_account(account):
            success_count += 1
        print("\n" + "="*50 + "\n")  # 账户分隔线
        time.sleep(1)  # 账户间短暂延迟
    
    print(f"\n📊 签到完成: 成功 {success_count}/{len(accounts)} 个账户")
    print("="*50)
