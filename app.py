import streamlit as st
from openai import OpenAI
import os
import json
from datetime import datetime
from supabase import create_client, Client

# ---------- 页面配置 ----------
st.set_page_config(page_title="SCR催化剂专家", page_icon="🧪", layout="wide")
# ---------- 隐藏右上角 GitHub 链接 ----------
st.markdown(
    """
    <style>
        .stApp header a[href*="github.com"] {
            display: none !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------- 初始化 Supabase 客户端 ----------
supabase: Client = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# ---------- 初始化 OpenAI 客户端 ----------
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

# ---------- 用户登录/注册 ----------
def init_auth():
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user is None:
        st.title("🔐 SCR催化剂智能助手")
        tab1, tab2 = st.tabs(["登录", "注册"])
        
        with tab1:
            email = st.text_input("邮箱", key="login_email")
            password = st.text_input("密码", type="password", key="login_password")
            if st.button("登录"):
                try:
                    resp = supabase.auth.sign_in_with_password({
                        "email": email, "password": password
                    })
                    user = resp.user
                    # 获取用户角色
                    profile_resp = supabase.table("user_profiles").select("role").eq("user_id", user.id).execute()
                    if profile_resp.data:
                        role = profile_resp.data[0]["role"]
                    else:
                        role = "user"  # 默认普通用户
                    st.session_state.user = {
                        "id": user.id,
                        "email": user.email,
                        "role": role
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"登录失败: {e}")

        with tab2:
            new_email = st.text_input("邮箱", key="reg_email")
            new_password = st.text_input("密码", type="password", key="reg_password")
            if st.button("注册"):
                try:
                    resp = supabase.auth.sign_up({
                        "email": new_email, "password": new_password
                    })
                    user = resp.user
                    # 默认角色为 'user'
                    supabase.table("user_profiles").insert({
                        "user_id": user.id,
                        "email": user.email,
                        "role": "user"
                    }).execute()
                    st.success("注册成功，请返回登录")
                except Exception as e:
                    st.error(f"注册失败: {e}")
        return False
    else:
        return True

# ---------- 会话管理（数据库版）----------
def get_all_sessions():
    user = st.session_state.user
    if user["role"] == "admin":
        # 管理员：查询所有记录
        resp = supabase.table("chat_sessions").select("*").order("created_at", desc=True).execute()
    else:
        # 普通用户：只查自己的
        resp = supabase.table("chat_sessions").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
    return resp.data

def load_session(session_id):
    resp = supabase.table("chat_sessions").select("*").eq("session_id", session_id).execute()
    if resp.data:
        return resp.data[0]
    return None

def save_session(session_id, messages, title):
    user = st.session_state.user
    data = {
        "user_id": user["id"],
        "user_email": user["email"],
        "session_id": session_id,
        "title": title,
        "messages": json.dumps(messages, ensure_ascii=False)  # 转成 JSON 字符串
    }
    # 如果该 session_id 已存在，则更新；否则插入
    existing = supabase.table("chat_sessions").select("id").eq("session_id", session_id).execute()
    if existing.data:
        supabase.table("chat_sessions").update(data).eq("session_id", session_id).execute()
    else:
        supabase.table("chat_sessions").insert(data).execute()

def delete_session(session_id):
    supabase.table("chat_sessions").delete().eq("session_id", session_id).execute()

def delete_all_sessions():
    user = st.session_state.user
    if user["role"] == "admin":
        # 管理员可以删除全部（谨慎）
        supabase.table("chat_sessions").delete().neq("id", 0).execute()  # 删除所有
    else:
        supabase.table("chat_sessions").delete().eq("user_id", user["id"]).execute()

def generate_title(messages):
    for msg in messages:
        if msg["role"] == "user":
            title = msg["content"][:30]
            return title + "..." if len(msg["content"]) > 30 else title
    return "新对话"

# ---------- 侧边栏 ----------
def render_sidebar():
    with st.sidebar:
        st.sidebar.success(f"👤 {st.session_state.user['email']} ({st.session_state.user['role']})")
        if st.button("🚪 退出登录", use_container_width=True):
            st.session_state.user = None
            st.rerun()

        st.header("📜 历史对话")

        if st.button("➕ 新建对话", use_container_width=True):
            st.session_state.messages = [{"role": "assistant", "content": "你好！我是SCR催化剂专家。请问有什么可以帮您？😊"}]
            st.session_state.current_session = None

        sessions = get_all_sessions()

        if not sessions:
            st.info("暂无历史对话")
        else:
            for sess in sessions:
                title = sess.get("title", "未命名")
                session_id = sess["session_id"]
                # 如果是管理员，显示记录来自哪个用户
                if st.session_state.user["role"] == "admin" and sess.get("user_email"):
                    display_title = f"{title} ({sess['user_email']})"
                else:
                    display_title = title
                if st.button(f"💬 {display_title}", key=session_id, use_container_width=True):
                    st.session_state.messages = json.loads(sess["messages"])
                    st.session_state.current_session = session_id

        st.divider()
        if st.button("🗑️ 清空所有历史", use_container_width=True):
            delete_all_sessions()
            st.session_state.messages = [{"role": "assistant", "content": "你好！我是SCR催化剂专家。请问有什么可以帮您？😊"}]
            st.session_state.current_session = None
            st.rerun()

# ---------- 主程序 ----------
def main():
    if not init_auth():
        return

    render_sidebar()

    # ---------- 主界面 ----------
    st.title("🧪 SCR脱硝催化剂智能助手")
    st.caption("SCR 催化剂智能助手 | 内部使用")

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

                # 自动保存
                title = generate_title(st.session_state.messages)
                if st.session_state.current_session is None:
                    session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(hash(title))[:6]
                    st.session_state.current_session = session_id
                save_session(st.session_state.current_session, st.session_state.messages, title)
                st.rerun()

if __name__ == "__main__":
    main()
