import os
import httpx
import json
import time
import re

# 从环境变量获取多账户 Cookie 配置
def get_cookies_list_from_env():
    """从环境变量解析多账户 Cookie"""
    cookies_list = []
    
    # 从环境变量中获取配置
    cookie_str = os.getenv('BDZYYI_COOKIES', '')
    if not cookie_str:
        print("❌ 错误：请设置环境变量 BDZYYI_COOKIES")
        return cookies_list
    
    # 支持多种分隔符：@、&、换行符
    separator = "@" if "@" in cookie_str else "&" if "&" in cookie_str else "\n"
    
    # 分割账户
    accounts = [acc.strip() for acc in cookie_str.split(separator) if acc.strip()]
    
    for index, account in enumerate(accounts, 1):
        cookies = {}
        # 支持两种格式：1. 完整 Cookie 字符串 2. JSON 格式
        if account.startswith("{") and account.endswith("}"):
            try:
                # JSON 格式解析
                cookie_json = json.loads(account)
                cookies = {k.strip(): v.strip() for k, v in cookie_json.items()}
            except json.JSONDecodeError:
                print(f"❌ 账户 {index}：JSON 格式解析失败，尝试作为字符串解析")
                # 尝试作为字符串解析
                for item in account.split(';'):
                    if '=' in item:
                        key, value = item.split('=', 1)
                        cookies[key.strip()] = value.strip()
        else:
            # 字符串格式解析
            for item in account.split(';'):
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key.strip()] = value.strip()
        
        if not cookies:
            print(f"❌ 账户 {index}：Cookie 格式无效")
            continue
        
        # 验证必需的 Cookie 键
        required_keys = ["PHPSESSID"]
        if not any("wordpress_logged_in" in key for key in cookies.keys()):
            required_keys.append("wordpress_logged_in_xxx")
        
        missing_keys = [key for key in required_keys if key not in cookies]
        if missing_keys:
            print(f"❌ 账户 {index}：缺少必需的 Cookie 键: {', '.join(missing_keys)}")
            continue
        
        cookies_list.append({
            "cookies": cookies,
            "id": index
        })
    
    return cookies_list

# 🔧 请求头
def get_headers():
    """生成随机用户代理的请求头"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
    ]
    
    return {
        "Host": "vip.bdziyi.com",
        "User-Agent": random.choice(user_agents),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://vip.bdziyi.com",
        "Referer": "https://vip.bdziyi.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }

# 📦 表单数据
data = {
    "action": "user_checkin"
}

# 🔗 请求 URL
url = "https://vip.bdziyi.com/wp-admin/admin-ajax.php"

def sign_in_for_account(account):
    """为单个账户执行签到"""
    account_id = account["id"]
    cookies = account["cookies"]
    
    print(f"\n{'='*30} 账户 {account_id} {'='*30}")
    
    try:
        # 获取登录用户名（如果有）
        username = "未知用户"
        for key in cookies:
            if "wordpress_logged_in" in key:
                # 尝试从 Cookie 值中提取用户名
                match = re.search(r'\|([^\|]+)\|', cookies[key])
                if match:
                    username = match.group(1)
                    break
        
        print(f"👤 用户名: {username}")
        print(f"🔑 使用的 Cookie 键: {', '.join(cookies.keys())}")
        
        # 📨 发起 POST 请求
        with httpx.Client(
            http2=True,
            cookies=cookies,
            headers=get_headers(),
            timeout=15,
            follow_redirects=True
        ) as client:
            start_time = time.time()
            response = client.post(url, data=data)
            elapsed_time = (time.time() - start_time) * 1000  # 毫秒
        
        print(f"⏱️ 请求耗时: {elapsed_time:.2f}ms")
        print(f"📡 响应状态码: {response.status_code}")
        
        # 📊 处理响应
        if response.status_code == 200:
            try:
                result = response.json()
                
                if not result.get("error"):
                    print("✅ 签到成功！🎉")
                    print(f"📅 连续签到: {result.get('continuous_day', '未知')} 天")
                    print(f"⭐ 获得积分: +{result.get('data', {}).get('points', '未知')}")
                    print(f"📚 获得经验: +{result.get('data', {}).get('integral', '未知')}")
                    print(f"🕒 时间: {result.get('data', {}).get('time', '未知')}")
                    return True
                else:
                    error_msg = result.get("msg", "未知错误")
                    print(f"❌ 签到失败: {error_msg}")
                    
                    # 常见错误处理
                    if "已经签到" in error_msg:
                        print("ℹ️ 今日已签到过，无需重复签到")
                        return True
                    elif "登录" in error_msg:
                        print("⚠️ Cookie 可能已失效，请重新获取")
            except json.JSONDecodeError:
                print("❌ 无法解析返回结果，响应内容:")
                print(response.text[:200])  # 只打印前200个字符
        else:
            print(f"🚫 请求失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text[:200]}")
    
    except httpx.ConnectError:
        print("❌ 网络连接错误，请检查网络连接")
    except httpx.TimeoutException:
        print("❌ 请求超时，请稍后重试")
    except Exception as e:
        print(f"❌ 发生未知错误: {str(e)}")
    
    return False

if __name__ == "__main__":
    # 获取多账户配置
    accounts = get_cookies_list_from_env()
    
    if not accounts:
        print("❌ 没有有效的账户配置，脚本终止")
        exit(1)
    
    print(f"🔍 找到 {len(accounts)} 个有效账户")
    print("=" * 60)
    
    # 执行签到
    success_count = 0
    for account in accounts:
        if sign_in_for_account(account):
            success_count += 1
        print("=" * 60)
        time.sleep(1)  # 账户间短暂延迟
    
    print(f"\n📊 签到完成: 成功 {success_count}/{len(accounts)} 个账户")
    print("=" * 60)
