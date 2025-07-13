import os
import requests
from PIL import Image
from io import BytesIO
import base64
import time
import random
import re
from bs4 import BeautifulSoup
import json
import sys

# 所需依赖 requests pillow

# 从环境变量获取配置
ACCOUNTS = os.environ.get('XSJ_ACCOUNTS', '')  # 多账户配置
OCR_SERVICE = os.environ.get('OCR_SERVICE', '')
main_url = "https://xsijishe.com"
TIMEOUT = 10
MAX_RETRY = 3

# 调试信息
print(f"环境变量 XSJ_ACCOUNTS 长度: {len(ACCOUNTS)}")
print(f"环境变量 OCR_SERVICE: {OCR_SERVICE}")

# 检查环境变量是否设置
if not ACCOUNTS.strip() or not OCR_SERVICE.strip():
    print("❌ 错误：环境变量 XSJ_ACCOUNTS 或 OCR_SERVICE 未设置或为空")
    print("请确保在运行环境中正确设置了这两个环境变量")
    sys.exit(1)

# 登录用到的参数
sign_url = '/k_misign-sign.html'

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

def get_random_user_agent():
    """生成随机User-Agent"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
    ]
    return random.choice(user_agents)

def get_session_headers():
    """获取会话请求头"""
    return {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": main_url
    }

def recognize_captcha(base64_img):
    """识别验证码"""
    if "," in base64_img:
        base64_img = base64_img.split(",", 1)[1]
    try:
        resp = requests.post(OCR_SERVICE, json={"image": base64_img}, timeout=TIMEOUT)
        if resp.ok:
            # 确保验证码长度为4位
            result = resp.json().get("result", "").strip()
            # 过滤无效字符，只保留字母和数字
            return re.sub(r'[^a-zA-Z0-9]', '', result)[:4]
        return ""
    except Exception as e:
        print(f"🤖 OCR识别错误: {e}")
        return ""

def get_form_info(session):
    """获取登录表单信息"""
    for _ in range(MAX_RETRY):
        try:
            # 第一步：获取登录页面
            login_page_url = f"{main_url}/member.php?mod=logging&action=login"
            r = session.get(login_page_url, timeout=TIMEOUT)
            r.raise_for_status()
            
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # 获取formhash
            formhash_input = soup.find('input', {'name': 'formhash'})
            formhash = formhash_input['value'] if formhash_input else None
            
            # 获取referer
            referer_input = soup.find('input', {'name': 'referer'})
            referer = referer_input['value'] if referer_input else main_url
            
            # 获取seccodehash
            seccode_span = soup.find('span', id=re.compile(r'^seccode_'))
            if seccode_span:
                seccodehash = seccode_span['id'].replace('seccode_', '')
            else:
                # 备选方案：从验证码图片URL中提取
                captcha_img = soup.find('img', id=re.compile(r'^seccode_'))
                if captcha_img and 'src' in captcha_img.attrs:
                    src = captcha_img['src']
                    match = re.search(r'idhash=([a-zA-Z0-9]+)', src)
                    seccodehash = match.group(1) if match else None
            
            # 获取登录表单的action URL
            login_form = soup.find('form', {'id': 'loginform'})
            login_action = login_form['action'] if login_form and 'action' in login_form.attrs else None
            
            if formhash and seccodehash and referer and login_action:
                print(f"📝 获取登录参数成功: formhash={formhash}, seccodehash={seccodehash}")
                return formhash, seccodehash, referer, login_action
            
            print("⚠️ 部分登录参数缺失，重试中...")
            time.sleep(2)
        except Exception as e:
            print(f"⚠️ 获取登录参数失败: {e}")
            time.sleep(2)
    
    print("❌ 无法获取登录参数，达到最大重试次数")
    return None, None, None, None

def check_captcha(session, seccodehash, seccodeverify):
    """检查验证码是否正确"""
    url = f"{main_url}/misc.php"
    params = {
        "mod": "seccode",
        "action": "check",
        "inajax": "1",
        "modid": "member::logging",
        "idhash": seccodehash,
        "secverify": seccodeverify
    }
    try:
        r = session.get(url, params=params, timeout=TIMEOUT)
        # 更严格的验证码校验
        if "succeed" in r.text:
            return True
        # 检查是否有验证码错误提示
        if "验证码错误" in r.text or "验证码不正确" in r.text:
            print(f"❌ 验证码校验失败: {seccodeverify}")
            return False
        # 未知响应
        print(f"⚠️ 验证码校验未知响应: {r.text[:100]}")
        return False
    except Exception as e:
        print(f"❌ 验证码校验异常: {e}")
        return False

def login_account(username, password):
    """登录账户"""
    session = requests.Session()
    session.headers.update(get_session_headers())
    
    print(f"\n🔐 开始登录账户: {username}")
    
    for attempt in range(1, MAX_RETRY + 1):
        print(f"⏳ 尝试 #{attempt}")
        
        # 获取登录参数
        formhash, seccodehash, referer, login_action = get_form_info(session)
        if not formhash or not seccodehash or not login_action:
            print("❌ 缺少必要登录参数")
            continue
            
        # 获取验证码
        captcha_url = f"{main_url}/misc.php?mod=seccode&update={int(time.time())}&idhash={seccodehash}"
        try:
            captcha_resp = session.get(captcha_url, timeout=TIMEOUT)
            if "image" not in captcha_resp.headers.get("Content-Type", ""):
                print("❗ 验证码图片响应异常")
                time.sleep(2)
                continue
        except Exception as e:
            print(f"❌ 获取验证码失败: {e}")
            time.sleep(2)
            continue
        
        # 识别验证码
        img = Image.open(BytesIO(captcha_resp.content))
        buffer = BytesIO()
        img.save(buffer, format="JPEG")
        base64_img = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()
        
        seccodeverify = recognize_captcha(base64_img)
        if not seccodeverify or len(seccodeverify) != 4:
            print(f"🤖 验证码识别失败: {seccodeverify}")
            time.sleep(2)
            continue
        
        print(f"✅ 验证码识别成功: {seccodeverify}")
        
        # 检查验证码
        if not check_captcha(session, seccodehash, seccodeverify):
            print(f"❌ 验证码校验失败: {seccodeverify}")
            time.sleep(2)
            continue
        
        # 构建登录请求
        login_url = f"{main_url}{login_action}"
        payload = {
            "formhash": formhash,
            "referer": referer,
            "username": username,
            "password": password,
            "questionid": "0",
            "answer": "",
            "seccodehash": seccodehash,
            "seccodemodid": "member::logging",
            "seccodeverify": seccodeverify,
            "loginsubmit": "true"
        }
        
        try:
            # 添加登录来源字段
            payload["cookietime"] = "2592000"
            
            r = session.post(login_url, data=payload, timeout=15)
            
            # 处理XML格式的响应
            if "<?xml" in r.text:
                # 从XML中提取错误信息
                cdata_match = re.search(r'<!\[CDATA\[(.*?)\]\]>', r.text, re.DOTALL)
                if cdata_match:
                    error_content = cdata_match.group(1)
                    if "欢迎您回来" in error_content or "登录成功" in error_content:
                        print(f"🎉 账户 {username} 登录成功！")
                        return session
                    else:
                        # 提取错误信息
                        error_match = re.search(r'<font color="red">(.*?)</font>', error_content)
                        if error_match:
                            error_msg = error_match.group(1)
                            print(f"❌ 登录失败: {error_msg}")
                            # 检查是否账号密码错误
                            if "密码错误" in error_msg or "用户名无效" in error_msg:
                                print(f"❌ 账号或密码错误，停止重试")
                                return None
                        else:
                            print(f"❌ 登录失败: {error_content[:100]}...")
                else:
                    print(f"❌ 登录失败，未知XML响应: {r.text[:100]}...")
            else:
                # 处理HTML格式的响应
                if "欢迎您回来" in r.text or "登录成功" in r.text:
                    print(f"🎉 账户 {username} 登录成功！")
                    return session
                else:
                    # 尝试解析错误信息
                    soup = BeautifulSoup(r.text, 'html.parser')
                    error_msg = soup.find('div', class_='alert_error')
                    if error_msg:
                        error_text = error_msg.get_text(strip=True)
                        print(f"❌ 登录失败: {error_text}")
                        # 检查是否账号密码错误
                        if "密码错误" in error_text or "用户名无效" in error_text:
                            print(f"❌ 账号或密码错误，停止重试")
                            return None
                    else:
                        print(f"❌ 登录失败，未知响应: {r.text[:100]}...")
        except Exception as e:
            print(f"❌ 登录请求异常: {e}")
        
        time.sleep(3)
    
    print(f"❌ 账户 {username} 登录失败，达到最大重试次数")
    return None

def do_sign_in(session):
    """执行签到操作"""
    print("\n⏳ 开始签到流程...")
    
    # 访问签到页面获取formhash
    sign_page_url = f"{main_url}{sign_url}"
    try:
        r = session.get(sign_page_url, timeout=TIMEOUT)
        r.raise_for_status()
        
        # 检查是否已签到
        if "您今天已经签到过了" in r.text or "今日已签" in r.text:
            print("✅ 今日已签到")
            return 0  # 已签到状态
        
        # 解析formhash
        soup = BeautifulSoup(r.text, 'html.parser')
        formhash_input = soup.find('input', {'name': 'formhash'})
        if not formhash_input:
            print("❌ 无法找到formhash")
            return 2  # 失败状态
        
        formhash = formhash_input['value']
        print(f"📝 获取签到formhash: {formhash}")
        
        # 提交签到请求
        sign_action_url = f"{main_url}/plugin.php?id=k_misign:sign&operation=qiandao&formhash={formhash}&format=empty"
        sign_data = {
            "formhash": formhash,
            "qdxq": random.choice(["kx", "ng", "ym", "wl", "nu", "ch", "fd", "yl", "shuai"]),
            "qdmode": "1",
            "todaysay": "",
            "fastreply": "0"
        }
        
        r = session.post(sign_action_url, data=sign_data, timeout=TIMEOUT)
        r.raise_for_status()
        
        # 检查签到结果
        if "签到成功" in r.text:
            print("🎉 签到成功")
            return 1  # 成功状态
        elif "您今天已经签到过了" in r.text:
            print("✅ 今日已签到")
            return 0  # 已签到状态
        else:
            print(f"❌ 签到失败: {r.text[:200]}")
            return 2  # 失败状态
    
    except Exception as e:
        print(f"❌ 签到过程中出错: {e}")
        return 2  # 失败状态

def get_user_info(session, username, checkIn_status):
    """获取用户信息"""
    print("\n🔍 获取用户信息...")
    
    # 访问签到页面获取用户数据
    sign_page_url = f"{main_url}{sign_url}"
    try:
        r = session.get(sign_page_url, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # 获取用户信息
        user_name = "未知用户"
        user_link = soup.find('a', href=re.compile(r'home.php\?mod=space'))
        if user_link:
            user_name = user_link.get_text(strip=True)
        
        # 获取签到信息
        sign_info = {
            "qiandao_num": "未知",
            "lxdays": "未知",
            "lxtdays": "未知",
            "lxlevel": "未知",
            "lxreward": "未知"
        }
        
        # 尝试从签到页面获取数据
        for key in sign_info.keys():
            element = soup.find('input', {'id': key})
            if element and 'value' in element.attrs:
                sign_info[key] = element['value']
        
        # 访问个人主页获取更多信息
        profile_url = f"{main_url}/home.php?mod=space"
        r = session.get(profile_url, timeout=TIMEOUT)
        r.raise_for_status()
        profile_soup = BeautifulSoup(r.text, 'html.parser')
        
        # 获取用户积分信息
        stats = {
            "积分": "未知",
            "威望": "未知",
            "车票": "未知",
            "贡献": "未知"
        }
        
        # 尝试查找积分信息
        stats_container = profile_soup.find('ul', id='psts')
        if stats_container:
            for li in stats_container.find_all('li'):
                text = li.get_text(strip=True)
                for key in stats:
                    if key in text:
                        stats[key] = text.replace(key, "").strip()
        
        # 构建用户信息字符串
        checkIn_content = ["已签到", "签到成功", "签到失败"]
        info_text = (
            f"======== 账户【{user_name}】 ========\n"
            f"📌 用户名: {username}\n"
            f"📌 签到状态: {checkIn_content[checkIn_status]}\n\n"
            f"📊 签到信息:\n"
            f"  签到排名: {sign_info['qiandao_num']}\n"
            f"  签到等级: Lv.{sign_info['lxlevel']}\n"
            f"  连续签到: {sign_info['lxdays']} 天\n"
            f"  签到总数: {sign_info['lxtdays']} 天\n"
            f"  签到奖励: {sign_info['lxreward']}\n\n"
            f"💎 账户资产:\n"
            f"  积分: {stats['积分']}\n"
            f"  威望: {stats['威望']}\n"
            f"  车票: {stats['车票']}\n"
            f"  贡献: {stats['贡献']}\n"
            f"==============================\n"
        )
        
        print(info_text)
        return True
    
    except Exception as e:
        print(f"❌ 获取用户信息失败: {e}")
        return False

def process_account(account):
    """处理单个账户"""
    username = account["username"]
    password = account["password"]
    
    print(f"\n{'='*50}")
    print(f"🚀 开始处理账户: {username}")
    print(f"{'='*50}")
    
    # 登录账户
    session = login_account(username, password)
    if not session:
        print(f"❌ 账户 {username} 处理失败")
        return False
    
    # 执行签到
    checkIn_status = do_sign_in(session)
    
    # 获取用户信息
    get_user_info(session, username, checkIn_status)
    
    print(f"✅ 账户 {username} 处理完成\n")
    return True

if __name__ == "__main__":
    # 解析多账户配置
    accounts = parse_accounts(ACCOUNTS)
    
    if not accounts:
        print("❌ 没有找到有效的账户配置")
        print(f"原始账户字符串: {ACCOUNTS[:50]}...")
        sys.exit(1)
    
    print(f"🔍 找到 {len(accounts)} 个账户")
    
    # 处理每个账户
    success_count = 0
    for account in accounts:
        if process_account(account):
            success_count += 1
        time.sleep(random.uniform(1, 3))  # 账户间随机延迟
    
    print(f"\n✅ 所有账户处理完成，成功: {success_count}/{len(accounts)}")
