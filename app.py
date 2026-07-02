import streamlit as st
from openai import OpenAI
import os
import json
from datetime import datetime
import hashlib

# ---------- 页面配置 ----------
st.set_page_config(page_title="SCR催化剂专家", page_icon="🧪", layout="wide")

# ---------- 简单密码登录配置 ----------
# ⚠️ 请修改为你想用的密码！
PASSWORD = "scr2024"  # 比如 "scr123456"

def check_password():
    """验证密码"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔐 SCR催化剂智能助手")
        st.markdown("请输入密码以继续使用")
        
        password_input = st.text_input("密码", type="password", placeholder="请输入密码")
        
        if st.button("登录", use_container_width=True):
            if password_input == PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ 密码错误，请重试")
        
        st.caption("内部使用 · 请联系管理员获取密码")
        return False
    
    return True

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
    for msg in messages:
        if msg["role"] == "user":
            title = msg["content"][:30]
            return title + "..." if len(msg["content"]) > 30 else title
    return "新对话"

# ---------- 主程序 ----------
def main():
    # 检查登录状态
    if not check_password():
        return
    
    # ---------- 侧边栏 ----------
    with st.sidebar:
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
        
        # 显示退出登录按钮
        if st.button("🚪 退出登录", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

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
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

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

                title = generate_title(st.session_state.messages)
                if st.session_state.current_session is None:
                    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                    st.session_state.current_session = session_id
                save_session(st.session_state.current_session, st.session_state.messages, title)

if __name__ == "__main__":
    main()
