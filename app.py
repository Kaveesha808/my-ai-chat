import streamlit as st
import google.generativeai as genai
import json
import os
import uuid
from datetime import datetime

# --- Constants ---
DB_FILE = "chat_db.json"

# --- Database Management (JSON) ---
def load_db():
    if not os.path.exists(DB_FILE):
        # Default Data Structure
        default_db = {
            "api_keys": {},
            "personas": {
                "Default Assistant": "You are a helpful and friendly AI assistant.",
                "Python Expert": "You are an expert Python developer. You write clean, efficient code.",
                "Sarcastic Friend": "You are a sarcastic friend who makes jokes but still helps."
            },
            "chats": {}
        }
        with open(DB_FILE, "w") as f:
            json.dump(default_db, f)
        return default_db
    
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Load Data
db = load_db()

# --- Page Config ---
st.set_page_config(page_title="Ultra Gemini Chat", page_icon="🚀", layout="wide")

# --- Sidebar: Management Console ---
with st.sidebar:
    st.title("🎛️ Control Panel")

    # --- 1. API Key Manager ---
    with st.expander("🔑 API Key Manager", expanded=True):
        existing_keys = list(db["api_keys"].keys())
        selected_key_name = st.selectbox("Select API Key", ["None"] + existing_keys, index=0 if not existing_keys else 0)
        
        # Add New Key
        new_key_name = st.text_input("New Key Name (e.g. Work)")
        new_key_value = st.text_input("Paste API Key", type="password")
        if st.button("Save New Key"):
            if new_key_name and new_key_value:
                db["api_keys"][new_key_name] = new_key_value
                save_db(db)
                st.success("Key Saved!")
                st.rerun()

    # --- 2. Persona Manager ---
    with st.expander("🎭 Persona Manager", expanded=True):
        persona_names = list(db["personas"].keys())
        selected_persona = st.selectbox("Select Persona", persona_names)
        
        # Add/Edit Persona
        st.divider()
        st.caption("Create New Persona")
        new_p_name = st.text_input("Persona Name")
        new_p_prompt = st.text_area("System Instruction")
        if st.button("Save Persona"):
            if new_p_name and new_p_prompt:
                db["personas"][new_p_name] = new_p_prompt
                save_db(db)
                st.success("Persona Added!")
                st.rerun()

    # --- 3. Chat History Manager ---
    st.divider()
    st.subheader("🗂️ Saved Chats")
    
    if st.button("➕ Start New Chat", use_container_width=True):
        new_chat_id = str(uuid.uuid4())
        db["chats"][new_chat_id] = {
            "title": f"New Chat {datetime.now().strftime('%H:%M')}",
            "messages": []
        }
        save_db(db)
        st.session_state["current_chat_id"] = new_chat_id
        st.rerun()

    # List existing chats
    chat_ids = list(db["chats"].keys())
    if chat_ids:
        # Sort by latest logic could be added here
        selected_chat_id = st.radio(
            "Select Chat:",
            chat_ids,
            format_func=lambda x: db["chats"][x]["title"],
            key="chat_radio"
        )
        # Update session state if radio changes
        if "current_chat_id" not in st.session_state or st.session_state["current_chat_id"] != selected_chat_id:
             st.session_state["current_chat_id"] = selected_chat_id

    # Delete Chat Option
    if "current_chat_id" in st.session_state:
         if st.button("🗑️ Delete Current Chat", type="primary"):
             del db["chats"][st.session_state["current_chat_id"]]
             save_db(db)
             del st.session_state["current_chat_id"]
             st.rerun()

# --- Main Logic ---

# Check if a chat is selected
if "current_chat_id" not in st.session_state or st.session_state["current_chat_id"] not in db["chats"]:
    st.info("👈 Please create a 'New Chat' or select one from the sidebar to start.")
    st.stop()

current_chat_id = st.session_state["current_chat_id"]
current_chat_data = db["chats"][current_chat_id]

# Title Edit
new_title = st.text_input("Chat Title", value=current_chat_data["title"], label_visibility="collapsed")
if new_title != current_chat_data["title"]:
    db["chats"][current_chat_id]["title"] = new_title
    save_db(db)
    st.rerun() # Refresh sidebar name

# Display Chat History
for msg in current_chat_data["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Chat Input ---
if prompt := st.chat_input("Type a message..."):
    
    # 1. Validation
    if selected_key_name == "None":
        st.error("Please select or add an API Key in the sidebar first!")
        st.stop()
        
    api_key = db["api_keys"][selected_key_name]
    system_instruction = db["personas"][selected_persona]

    # 2. Setup Gemini
    genai.configure(api_key=api_key)
    
    # Create Model
    model = genai.GenerativeModel(
        model_name="Gemini-2.5-Flash",
        system_instruction=system_instruction
    )

    # 3. Display User Message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Update DB (User)
    db["chats"][current_chat_id]["messages"].append({"role": "user", "content": prompt})
    save_db(db)

    # 4. Generate Response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # Prepare History for Gemini (excluding system prompts which are set in init)
            gemini_history = [
                {"role": m["role"], "parts": [m["content"]]} 
                for m in current_chat_data["messages"]
            ]
            
            # Since we just appended the user message to DB, pass history WITHOUT the last one to start_chat
            # and send the last one as the new message
            chat_session = model.start_chat(history=gemini_history[:-1])
            response = chat_session.send_message(prompt, stream=True)
            
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            
            # Update DB (Assistant)
            db["chats"][current_chat_id]["messages"].append({"role": "model", "content": full_response})
            save_db(db)
            
        except Exception as e:
            st.error(f"Error: {e}")
