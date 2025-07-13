import os
import requests
import base64
import json
from Cryptodome.Cipher import AES
from Cryptodome.Hash import SHA256
#需要安装pycryptodomex
#第一次使用前先抓https://bxo30.xyz/api/user/qd请求中的encryptedData和iv参数将其填到环境变量中

# 从环境变量获取配置
MHS_ACCOUNTS = os.environ.get('MHS_ACCOUNTS', '')  # 多账户配置
TOKEN_FILE_PREFIX = "./mhs_"  # token文件前缀

# 检查环境变量是否设置
if not MHS_ACCOUNTS:
    print("❌ 错误：请设置环境变量 MHS_ACCOUNTS")
    exit(1)

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
        parts = account_str.split(":", 3)
        
        if len(parts) < 4:
            print(f"❌ 账户信息不完整: {account_str}")
            continue
            
        username = parts[0].strip()
        password = parts[1].strip()
        encrypted_data = parts[2].strip()
        iv = parts[3].strip()
        
        accounts.append({
            "username": username,
            "password": password,
            "encrypted_data": encrypted_data,
            "iv": iv
        })
    
    return accounts

def save_token(username, token):
    """保存token到文件"""
    token_file = f"{TOKEN_FILE_PREFIX}{username}.txt"
    try:
        with open(token_file, 'w', encoding='utf-8') as f:
            f.write(token)
        print(f"✅ Token已保存: {token_file}")
    except Exception as e:
        print(f"❌ Token保存失败: {e}")

def load_token(username):
    """从文件加载token"""
    token_file = f"{TOKEN_FILE_PREFIX}{username}.txt"
    if os.path.exists(token_file):
        try:
            with open(token_file, 'r', encoding='utf-8') as f:
                token = f.read().strip()
                if token:
                    print(f"✅ 已加载Token: {token_file}")
                    return token
        except Exception as e:
            print(f"❌ Token加载失败: {e}")
    return None

def login(username, password):
    """登录获取token"""
    headers = {
        "Host": "bxo30.xyz",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.70 Safari/537.36",
        "Origin": "https://bxo30.xyz",
        "Referer": "https://bxo30.xyz/",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }

    data = {
        "userName": username,
        "password": password
    }

    url = "https://bxo30.xyz/api/auth/login"
    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        if response.status_code == 200:
            print(f'🤪 登录结果：{response.json().get("msg")}')
        else:
            print(f'☹️ 登录失败，状态码：{response.status_code}')
            return None

        plaintext = decrypt_aes_cbc_base64(response.json().get("data"), response.json().get("iv"))
        token = plaintext.get('token')
        if token:
            save_token(username, token)
        print(f"🤖 新token: {token}")
        return token
    except Exception as e:
        print(f"❌ 登录请求异常: {e}")
        return None

def qd(username, token, encrypted_data, iv):
    """执行签到"""
    url = "https://bxo30.xyz/api/user/qd"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Token": token,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://bxo30.xyz",
        "Referer": "https://bxo30.xyz/"
    }
    json_data = {
        "encryptedData": encrypted_data,
        "iv": iv
    }
    
    try:
        response = requests.post(url, headers=headers, json=json_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 1:
                print(f"🥳 签到成功: {data.get('msg')}")
                return True
            else:
                print(f"😖 签到失败: {data.get('msg')}")
                return False
        else:
            print(f"😖 请求失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 签到请求异常: {e}")
        return False

def decrypt_aes_cbc_base64(cipher_b64: str, iv_b64: str, mH: str = "mhs-1234-s981re-k071y2"):
    """解密数据"""
    try:
        key = SHA256.new(mH.encode()).digest()
        iv = base64.b64decode(iv_b64)
        ciphertext = base64.b64decode(cipher_b64)

        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_plaintext = cipher.decrypt(ciphertext)

        pad_len = padded_plaintext[-1]
        plaintext = padded_plaintext[:-pad_len].decode('utf-8')

        try:
            return json.loads(plaintext)
        except json.JSONDecodeError:
            return plaintext
    except Exception as e:
        print(f"😖 解密失败: {e}")
        return None

def get_user_info(token):
    """获取用户信息"""
    url = "https://bxo30.xyz/api/user/info"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Token": token,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://bxo30.xyz",
        "Referer": "https://bxo30.xyz/"
    }

    try:
        response = requests.post(url, headers=headers, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("code") == 1:
                data = decrypt_aes_cbc_base64(res_json.get("data"), res_json.get("iv"))
                return data
            else:
                print(f"😖 请求失败，消息: {res_json.get('msg')}")
        else:
            print(f"😖 HTTP请求失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 获取用户信息异常: {e}")
    return None

def lottery(token, data):
    """抽奖"""
    jf = data.get("jf") if data else 0
    if jf < 10:
        print("💀 积分不足，无法抽奖")
        return
    
    url = "https://bxo30.xyz/api/user/lottery"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Token": token
    }
    
    try:
        resp = requests.post(url, headers=headers, json={}, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            code = result.get("code")
            msg = result.get("msg")
            name = result.get("data", {}).get("name")
            if code == 1:
                if name:
                    print(f"😋 抽奖{msg}，奖品信息: {name}")
                else:
                    print("🥱 抽奖成功，但结果为空")
            else:
                print(msg)
        else:
            print(f"😖 抽奖发生错误, 错误码: {resp.status_code}")
    except Exception as e:
        print(f"❌ 抽奖请求异常: {e}")

def process_account(account):
    """处理单个账户"""
    username = account["username"]
    password = account["password"]
    encrypted_data = account["encrypted_data"]
    iv = account["iv"]
    
    print(f"\n======= 开始处理账户: {username} =======")
    
    # 加载token
    token = load_token(username)
    
    # 如果没有token或签到失败，尝试登录
    if not token:
        print(f"🤖 没有找到有效token，准备登录获取新token")
        token = login(username, password)
    
    # 执行签到
    if token:
        success = qd(username, token, encrypted_data, iv)
        if not success:
            print(f"😖 签到失败，尝试重新登录获取token")
            token = login(username, password)
            if token:
                success = qd(username, token, encrypted_data, iv)
    
    # 获取用户信息和抽奖
    if token:
        data = get_user_info(token)
        if data:
            print(f"🤑 当前积分: {data.get('jf')}")
            lottery(token, data)
    
    print(f"======= 账户 {username} 处理完成 =======\n")
    return success

if __name__ == "__main__":
    # 解析多账户配置
    accounts = parse_accounts(MHS_ACCOUNTS)
    
    if not accounts:
        print("❌ 没有找到有效的账户配置")
        exit(1)
    
    print(f"🔍 找到 {len(accounts)} 个账户")
    
    # 处理每个账户
    success_count = 0
    for account in accounts:
        if process_account(account):
            success_count += 1
    
    print(f"✅ 所有账户处理完成，成功: {success_count}/{len(accounts)}")
