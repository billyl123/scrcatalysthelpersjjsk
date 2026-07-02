import streamlit as st
from openai import OpenAI
import os
import json
from datetime import datetime
import requests
import urllib.parse
import secrets

# ---------- 页面配置 ----------
st.set_page_config(page_title="SCR催化剂专家", page_icon="🧪", layout="wide")

# ---------- OAuth 配置 ----------
# ⚠️ 重要：REDIRECT_URI 必须和你在 ModelScope OAuth 应用里填写的回调地址完全一致！
CLIENT_ID = os.environ.get('OAUTH_CLIENT_ID')
CLIENT_SECRET = os.environ.get('OAUTH_CLIENT_SECRET')
REDIRECT_URI = "https://scr-catalyst-auth.ms.show"  # 替换成你的实际地址
AUTHORIZATION_URL = "https://www.modelscope.cn/oauth/authorize"
TOKEN_URL = "https://www.modelscope.cn/oauth/token"
USER_INFO_URL = "https://www.modelscope.cn/apis/user/info"
SCOPES = "openid profile"

# ---------- 初始化 OpenAI 客户端 ----------
client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com"
)

# ---------- 会话管理 ----------
SESSION_DIR = "sessions"
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

def get_all_sessions():
    """返回所有会话文件列表（按修改时间倒序）"""
    files = [f for f in os.listdir(SESSION_DIR) if f.endswith('.json')]
    files.sort(key=lambda f: os.path.getmtime(os.path.join(SESSION_DIR, f)), reverse=True)
    return files

def load_session(session_id):
    filepath = os.path.join(SESSION_DIR, f"{session_id}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_session(session_id, messages, title):
    data = {
        "session_id": session_id,
        "title": title,
        "updated_at": datetime.now().isoformat(),
        "messages": messages
    }
    filepath = os.path.join(SESSION_DIR, f"{session_id}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_title(messages):
    """用第一条用户消息生成标题"""
    for msg in messages:
        if msg["role"] == "user":
            title = msg["content"][:30]
            return title + "..." if len(msg["content"]) > 30 else title
    return "新对话"

# ---------- 主应用逻辑 ----------
def main():
    # ---------- 1. 检查登录状态 ----------
    if 'user' not in st.session_state:
        st.session_state.user = None

    # ---------- 2. 处理 OAuth 回调 (获取 code) ----------
    query_params = st.query_params
    if 'code' in query_params and st.session_state.user is None:
        code = query_params['code']
        # 用 code 换取 access_token
        token_data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI,
        }
        try:
            # 1. 请求 Token
            token_response = requests.post(TOKEN_URL, data=token_data)
            token_response.raise_for_status()
            tokens = token_response.json()
            access_token = tokens.get('access_token')

            # 2. 获取用户信息
            headers = {'Authorization': f'Bearer {access_token}'}
            user_response = requests.get(USER_INFO_URL, headers=headers)
            user_response.raise_for_status()
            user_info = user_response.json()

            # 3. 保存用户信息到 session
            st.session_state.user = user_info
            # 4. 清除 URL 中的 code 参数
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"登录失败: {e}")

    # ---------- 3. 显示登录状态或登录按钮 ----------
    if not st.session_state.user:
        # 未登录：显示登录按钮
        st.title("🧪 SCR脱硝催化剂智能助手")
        st.info("请使用 ModelScope 账号登录以继续使用")
        
        # 生成随机的 state 参数防止 CSRF 攻击
        state = secrets.token_urlsafe(16)
        # 构建授权 URL
        params = {
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'scope': SCOPES,
            'state': state,
        }
        auth_url = f"{AUTHORIZATION_URL}?{urllib.parse.urlencode(params)}"
        # 显示登录按钮
        st.link_button("🔑 使用 ModelScope 账号登录", auth_url, use_container_width=True)
        st.caption("登录即表示您同意授权本应用获取您的公开信息")
        return  # 阻止未登录用户看到应用内容

    # ---------- 4. 用户已登录：显示完整应用 ----------
    # 侧边栏：用户信息
    with st.sidebar:
        st.sidebar.success(f"👤 欢迎, {st.session_state.user.get('name', st.session_state.user.get('login', '用户'))}!")
        if st.button("🚪 退出登录", use_container_width=True):
            st.session_state.user = None
            st.rerun()
        
        st.divider()
        st.header("📜 历史对话")

        if st.button("➕ 新建对话", use_container_width=True):
            st.session_state.messages = [{"role": "assistant", "content": "你好！我是SCR催化剂专家。请问有什么可以帮您？😊"}]
            st.session_state.current_session = None

        sessions = get_all_sessions()

        if not sessions:
            st.info("暂无历史对话")
        else:
            for file in sessions:
                session_id = file.replace('.json', '')
                data = load_session(session_id)
                if data:
                    title = data.get("title", "未命名")
                    if st.button(f"💬 {title}", key=session_id, use_container_width=True):
                        st.session_state.messages = data["messages"]
                        st.session_state.current_session = session_id

        st.divider()
        if st.button("🗑️ 清空所有历史", use_container_width=True):
            for file in sessions:
                os.remove(os.path.join(SESSION_DIR, file))
            st.session_state.messages = [{"role": "assistant", "content": "你好！我是SCR催化剂专家。请问有什么可以帮您？😊"}]
            st.session_state.current_session = None

    # ---------- 主界面 ----------
    st.title("🧪 SCR脱硝催化剂智能助手")
    st.caption("SCR 催化剂智能助手 | 内部使用")

    # ---------- 初始化 ----------
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "你好！我是SCR催化剂专家。请问有什么可以帮您？😊"}]
    if "current_session" not in st.session_state:
        st.session_state.current_session = None

    # 显示聊天记录
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # ---------- 输入 ----------
    if prompt := st.chat_input("请输入您的问题："):
        # 追加用户消息
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # 调用 API
        with st.chat_message("assistant"):
            with st.spinner("专家思考中..."):
                try:
                    system = "你是一个SCR脱硝催化剂领域的资深专家，用专业清晰的语言回答。"
                    api_messages = [{"role": "system", "content": system}] + st.session_state.messages[-10:]
                    response = client.chat.completions.create(
                        model="deepseek-v4-pro",
                        messages=api_messages,
                        reasoning_effort="high",
                        extra_body={"thinking": {"type": "enabled"}}
                    )
                    reply = response.choices[0].message.content
                except Exception as e:
                    reply = f"⚠️ 错误：{e}"

                st.write(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})

                # 自动保存
                title = generate_title(st.session_state.messages)
                if st.session_state.current_session is None:
                    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                    st.session_state.current_session = session_id
                save_session(st.session_state.current_session, st.session_state.messages, title)

if __name__ == "__main__":
    main()