import json

async def replace_all_developers(r_session, dev_content):
    # 1. Fetch all current messages for this specific session
    items = await r_session.get_items() #
    
    # 2. Separate messages to identify latest entries
    user_msgs = [m for m in items if m.get("role") == "user"]
    other_msgs = [m for m in items if m.get("role") not in ["user", "developer"]]
    
    cleaned_user_history = []
    
    # 3. Filter/Clean User Messages: Keep latest, scrub older ones
    for i, msg in enumerate(user_msgs):
        if i == len(user_msgs) - 1:
            # Keep the LATEST user message fully intact
            cleaned_user_history.append(msg)
        else:
            # For OLDER user messages, remove 'grade_details' from the JSON content
            try:
                # Parse the JSON string within the content field
                content_data = json.loads(msg["content"])
                if "grade_details" in content_data:
                    del content_data["grade_details"] # Targeted removal
                
                # Re-serialize back to string
                msg["content"] = json.dumps(content_data, ensure_ascii=False)
                cleaned_user_history.append(msg)
            except (json.JSONDecodeError, TypeError, KeyError):
                # Fallback if content isn't a valid JSON string
                cleaned_user_history.append(msg)

    # 4. REMOVE THE OLD SESSION DATA (Targeted)
    # Instead of flushdb(), delete only the key for THIS session ID
    # In RedisSession, the key is usually "session:{session_id}:items"
    session_key = f"session:{r_session.session_id}:items"
    await r_session.redis_client.delete(session_key)

    # 5. ADD FRESH CONTENT BACK
    # Add back non-user/non-developer roles (Assistant, Tools, etc.)
    if other_msgs:
        await r_session.add_items(other_msgs)
    
    # Add back the cleaned/filtered user history
    if cleaned_user_history:
        await r_session.add_items(cleaned_user_history)
    
    # Finally, add the single "fresh" developer message
    await r_session.add_items([{"role": "developer", "content": dev_content}])
