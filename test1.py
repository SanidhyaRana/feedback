import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import json
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_DATABASE'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT', 5432))
}

# Initialize OpenAI Client
try:
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
except Exception as e:
    st.error("OpenAI API Key missing or invalid in .env file.")
    client = None

# Constants
ROWS_PER_PAGE = 10

# --- DATABASE FUNCTIONS ---

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def fetch_das_data(limit=10, offset=0):
    """Fetch data with pagination"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get total count for pagination logic
    cursor.execute('SELECT COUNT(*) FROM public.das')
    total_rows = cursor.fetchone()[0]
    
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
        LIMIT %s OFFSET %s
    """
    
    cursor.execute(query, (limit, offset))
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    
    df = pd.DataFrame(rows, columns=columns)
    
    cursor.close()
    conn.close()
    return df, total_rows

def insert_feedback(conversation_id, industry, conversation, generic_fb, industry_fb, 
                    market_segment_fb, conversation_fb, approved_by, ai_notes=None):
    """Insert feedback including AI notes if desired"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Note: Ensure your DB table 'das_feedback' has a column for AI notes if you want to save it permanently.
        # If not, you might need to append it to conversationFeedback or ignore saving it.
        # For this example, I am appending it to 'conversationFeedback' if the column doesn't exist.
        
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

# --- AI FUNCTIONS ---

def get_ai_critique(conversation_text, current_feedbacks):
    """Call OpenAI to critique and improve feedback"""
    if not client:
        return "Error: OpenAI client not initialized."
    
    prompt = f"""
    You are a QA Lead auditing AI conversation logs. 
    
    CONTEXT:
    Conversation: {str(conversation_text)[:8000]} 
    (Conversation truncated if too long)
    
    CURRENT FEEDBACK DRAFT:
    1. Generic Feedback: {current_feedbacks.get('generic', 'N/A')}
    2. Industry Feedback: {current_feedbacks.get('industry', 'N/A')}
    3. Market Segment Feedback: {current_feedbacks.get('market', 'N/A')}
    4. Conversation Feedback: {current_feedbacks.get('conversation', 'N/A')}
    
    YOUR TASK:
    1. Review the feedback for clarity and quality.
    2. CATEGORY CHECK: Identify if any feedback is in the wrong category (e.g., industry-specific nuances placed in 'Generic').
    3. IMPROVEMENT: Rewrite the feedback to be more professional and actionable if necessary.
    
    Output Format:
    Provide a concise summary of suggestions or a rewritten version of the feedback fields that need changes.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o", # or gpt-3.5-turbo
            messages=[
                {"role": "system", "content": "You are a helpful QA assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- UI SETUP ---
st.set_page_config(page_title="DAS Feedback System", layout="wide")

st.markdown("""
    <style>
    .main { padding-top: 1rem; }
    h1 { color: #2E7D32; }
    .stTextArea textarea { font-size: 14px; }
    </style>
""", unsafe_allow_html=True)

st.title("🗂️ DAS Feedback Management System")

# Session State
if 'selected_row_data' not in st.session_state:
    st.session_state.selected_row_data = None
if 'editing' not in st.session_state:
    st.session_state.editing = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0
if 'ai_result' not in st.session_state:
    st.session_state.ai_result = ""

# --- VIEW MODE (TABLE) ---
if not st.session_state.editing:
    
    # Pagination controls
    offset = st.session_state.current_page * ROWS_PER_PAGE
    df, total_rows = fetch_das_data(limit=ROWS_PER_PAGE, offset=offset)
    
    # Top bar with pagination info
    c1, c2, c3 = st.columns([2, 6, 2])
    with c1:
        st.markdown(f"**Total Records: {total_rows}**")
    with c3:
        # Pagination Buttons
        col_prev, col_page, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("◀", disabled=st.session_state.current_page == 0):
                st.session_state.current_page -= 1
                st.rerun()
        with col_page:
            st.markdown(f"<div style='text-align: center'>Page {st.session_state.current_page + 1}</div>", unsafe_allow_html=True)
        with col_next:
            if (offset + ROWS_PER_PAGE) < total_rows:
                if st.button("▶"):
                    st.session_state.current_page += 1
                    st.rerun()

    # Table Display
    if len(df) > 0:
        display_df = df.copy()
        # Clean dates for display
        for col in ['createdAt', 'updatedAt']:
            if col in display_df.columns:
                display_df[col] = pd.to_datetime(display_df[col]).dt.strftime('%Y-%m-%d %H:%M')
        
        st.info("👆 **Click on a row to edit feedback**")
        
        event = st.dataframe(
            display_df,
            use_container_width=True,
            height=400,
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True
        )
        
        if len(event.selection.rows) > 0:
            # Save the specific row data to session state
            idx = event.selection.rows[0]
            st.session_state.selected_row_data = df.iloc[idx].to_dict()
            st.session_state.editing = True
            st.session_state.ai_result = "" # Clear previous AI result
            st.rerun()
    else:
        st.info("No records found.")

# --- EDIT MODE ---
else:
    if st.session_state.selected_row_data:
        row = st.session_state.selected_row_data
        
        # Navigation
        col_back, col_title = st.columns([1, 10])
        with col_back:
            if st.button("← Back"):
                st.session_state.editing = False
                st.session_state.selected_row_data = None
                st.rerun()
        with col_title:
            st.subheader(f"Editing Feedback for ID: {row['conversationId']}")

        st.divider()

        # Context (Conversation)
        with st.expander("📄 View Conversation Context (Source Data)", expanded=False):
            st.json(row['conversation'])

        # Form
        with st.form("feedback_form"):
            # Feedback Inputs
            c1, c2 = st.columns(2)
            with c1:
                generic_fb = st.text_area("Generic Feedback", value=row.get("genericFeedback") or "", height=150)
                industry_fb = st.text_area("Industry Feedback", value=row.get("industryFeedback") or "", height=150)
            with c2:
                market_fb = st.text_area("Market Segment Feedback", value=row.get("marketSegmentFeedback") or "", height=150)
                conv_fb = st.text_area("Conversation Feedback", value=row.get("conversationFeedback") or "", height=150)
            
            # --- AI SECTION ---
            st.markdown("### 🤖 AI Analysis")
            
            # If we haven't run AI yet, show button inside a container (outside form logic trick)
            # Since buttons inside forms submit the form, we use a trick or place it outside.
            # Best practice in Streamlit forms: Buttons trigger submit. 
            # So we will put the AI button OUTSIDE the form or treat it as a submit action.
            # Let's put it outside above the AI text area for better flow.
            
            ai_col1, ai_col2 = st.columns([1, 5])
            
            # Placeholder for the AI Output
            ai_output_area = st.empty()
            if st.session_state.ai_result:
                 st.info(st.session_state.ai_result, icon="🤖")

            st.divider()
            
            approved_by = st.text_input("Approved By *")
            
            # Form Buttons
            btn_col1, btn_col2 = st.columns([1, 5])
            with btn_col1:
                submit = st.form_submit_button("Submit & Save", type="primary", use_container_width=True)
            
            if submit:
                if not approved_by:
                    st.error("Approved By is required.")
                else:
                    success = insert_feedback(
                        row["conversationId"], row["industry"], row["conversation"],
                        generic_fb, industry_fb, market_fb, conv_fb, approved_by
                    )
                    if success:
                        st.success("Feedback saved successfully!")
                        st.session_state.editing = False
                        st.rerun()

        # AI Button (Outside Form to prevent auto-submission of form data)
        # We place this here so user can click it, get results, copy-paste into form fields if they want.
        st.markdown("---")
        st.markdown("**AI Helper Tools**")
        if st.button("✨ Analyze & Improve with AI"):
            with st.spinner("Analyzing conversation and feedback..."):
                current_inputs = {
                    "generic": row.get("genericFeedback"),
                    "industry": row.get("industryFeedback"),
                    "market": row.get("marketSegmentFeedback"),
                    "conversation": row.get("conversationFeedback")
                }
                
                # Call AI
                ai_feedback = get_ai_critique(row.get("conversation"), current_inputs)
                st.session_state.ai_result = ai_feedback
                st.rerun()