import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_DATABASE'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT', 5432))
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def fetch_das_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            "conversationId",
            industry,
            conversation::text as conversation,
            "genericFeedback",
            "industryFeedback",
            "marketSegmentFeedback",
            "conversationFeedback",
            "createdAt",
            "updatedAt"
        FROM public.das
        ORDER BY "createdAt" DESC
    """
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    df = pd.DataFrame(rows, columns=columns)
    cursor.close()
    conn.close()
    return df

def insert_feedback(conversation_id, industry, conversation, generic_fb, industry_fb, 
                    market_segment_fb, conversation_fb, approved_by):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
            INSERT INTO public.das_feedback 
            ("conversationId", industry, conversation, "genericFeedback", 
             "industryFeedback", "marketSegmentFeedback", "conversationFeedback", 
             "approvedBy")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        conversation_json = json.dumps(conversation) if isinstance(conversation, dict) else conversation
        cursor.execute(query, (conversation_id, industry, conversation_json, generic_fb, 
                              industry_fb, market_segment_fb, conversation_fb, approved_by))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Error inserting feedback: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

st.set_page_config(page_title="DAS Feedback System", layout="wide")

st.markdown("""
    <style>
    .main { padding-top: 1rem; }
    h1 { color: #2E7D32; padding-bottom: 1rem; }
    /* Highlight the selected row visually if needed */
    </style>
""", unsafe_allow_html=True)

st.title("🗂️ DAS Feedback Management System")

# Initialize session state
if 'selected_row_index' not in st.session_state:
    st.session_state.selected_row_index = None
if 'editing' not in st.session_state:
    st.session_state.editing = False

# --- VIEW MODE ---
if not st.session_state.editing:
    try:
        df = fetch_das_data()
        st.markdown(f"**Total Records: {len(df)}**")
        st.info("👆 **Click on any row to edit its feedback.**") # Instruction for user
        
        if len(df) > 0:
            display_df = df.copy()
            # Format dates
            for col in ['createdAt', 'updatedAt']:
                if col in display_df.columns:
                    display_df[col] = pd.to_datetime(display_df[col]).dt.strftime('%Y-%m-%d %H:%M')
            
            # --- NEW SELECTION LOGIC ---
            event = st.dataframe(
                display_df,
                use_container_width=True,
                height=600,
                on_select="rerun",           # Reruns script on click
                selection_mode="single-row", # Single selection
                hide_index=True
            )
            
            # If user clicked a row
            if len(event.selection.rows) > 0:
                st.session_state.selected_row_index = event.selection.rows[0]
                st.session_state.editing = True
                st.rerun()
                
        else:
            st.info("No records found.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")

# --- EDIT MODE ---
else:
    try:
        # Re-fetch data to ensure freshness (or you can cache the df in session_state)
        df = fetch_das_data()
        
        # Safety check
        if st.session_state.selected_row_index is not None and st.session_state.selected_row_index < len(df):
            row_data = df.iloc[st.session_state.selected_row_index]
            
            # Back Button
            col1, col2 = st.columns([1, 10])
            with col1:
                if st.button("← Back"):
                    st.session_state.editing = False
                    st.session_state.selected_row_index = None
                    st.rerun()
            
            st.markdown(f"### Editing Row #{st.session_state.selected_row_index + 1}")
            st.divider()
            
            # Read-only Info
            c1, c2 = st.columns(2)
            c1.info(f"**ID:** {row_data['conversationId']}")
            c2.info(f"**Industry:** {row_data['industry']}")
            
            with st.expander("View Full Conversation JSON"):
                st.json(row_data['conversation'])

            st.divider()

            # Form
            with st.form("feedback_form"):
                c1, c2 = st.columns(2)
                with c1:
                    generic_fb = st.text_area("Generic Feedback", value=row_data.get("genericFeedback") or "", height=150)
                    industry_fb = st.text_area("Industry Feedback", value=row_data.get("industryFeedback") or "", height=150)
                with c2:
                    market_fb = st.text_area("Market Segment Feedback", value=row_data.get("marketSegmentFeedback") or "", height=150)
                    conv_fb = st.text_area("Conversation Feedback", value=row_data.get("conversationFeedback") or "", height=150)
                
                approved_by = st.text_input("Approved By *")
                
                btn_col1, btn_col2 = st.columns([1, 5])
                with btn_col1:
                    submit = st.form_submit_button("Submit Feedback", type="primary", use_container_width=True)
                
                if submit:
                    if not approved_by:
                        st.error("Approved By is required.")
                    else:
                        success = insert_feedback(
                            row_data["conversationId"], row_data["industry"], row_data["conversation"],
                            generic_fb, industry_fb, market_fb, conv_fb, approved_by
                        )
                        if success:
                            st.success("Saved!")
                            st.session_state.editing = False
                            st.session_state.selected_row_index = None
                            st.rerun()
        else:
            st.warning("Selection lost. returning to table.")
            st.session_state.editing = False
            st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")