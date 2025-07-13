import requests
import time
import os

# 从青龙环境变量获取TOKEN列表
TOKENS = os.getenv('STARRY_TOKENS', '').split(',')
if not TOKENS or TOKENS == ['']:
    print("⚠️ 未检测到环境变量STARRY_TOKENS，请添加你的Token")
    exit(1)

# 基础配置
BASE_URL = "https://api.starrycoding.com"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.starrycoding.com",
    "Referer": "https://www.starrycoding.com/user/panel",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"
}


def sign_in(token):
    """执行签到操作"""
    print("📡 正在尝试签到...")
    sign_url = f"{BASE_URL}/user/task/sign"
    headers = {**HEADERS, "Token": token}
    
    try:
        response = requests.post(sign_url, headers=headers, timeout=10)
        if response.status_code == 201:
            result = response.json()
            if "data" in result and "coin" in result["data"]:
                coin = result["data"]["coin"]
                print(f"✅ 签到成功，获得 {coin} 枚星币 🎉")
                return True
            else:
                print(f"⚠️ 无法获取coin，完整响应: {result}")
        elif response.status_code == 400:
            print(f"⚠️ {response.json().get('msg', '今日已签到或请求异常')}")
        else:
            print(f"❌ 签到失败，状态码：{response.status_code}")
    except Exception as e:
        print(f"❌ 签到请求异常: {str(e)}")
    return False


def get_user_info(token):
    """获取用户信息"""
    print("\n📥 正在获取用户信息...")
    user_url = f"{BASE_URL}/user/token"
    headers = {**HEADERS, "Token": token}
    
    try:
        response = requests.get(user_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json().get("data", {})
            print(f"""
👤 用户名：{data.get('username', '未知')}
🪙 当前星币：{data.get('coin', 0)}
🏅 排名：{data.get('rank', '未知')}
📧 邮箱：{data.get('email', '未绑定')}
🕰️ 创建时间：{data.get('createdAt', '未知')}
            """)
            return True
    except Exception as e:
        print(f"❌ 获取用户信息异常: {str(e)}")
    return False


if __name__ == "__main__":
    print("🌟 StarryCoding 多账户签到脚本 🌟\n")
    print(f"🔑 检测到 {len(TOKENS)} 个账户\n")
    
    for index, token in enumerate(TOKENS, 1):
        token = token.strip()
        if not token:
            continue
            
        print(f"🔄 开始处理账户 #{index}/{len(TOKENS)}")
        sign_in(token)
        get_user_info(token)
        
        # 账户间延迟防止请求过快
        if index < len(TOKENS):
            print("\n⏳ 等待3秒处理下一个账户...")
            time.sleep(3)
            print("-" * 40 + "\n")
    
    print("\n✨ 所有账户处理完成！")
