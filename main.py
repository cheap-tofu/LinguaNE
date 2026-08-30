import gradio as gr
from gtts import gTTS
import pandas as pd
from google import genai
from google.genai import types
import json
import pathlib
import subprocess
import time
import os
import re
import concurrent.futures

# 1. CLEAN UP RUNNING SESSIONS
gr.close_all()

# 2. SETUP THE MULTI-KEY POOL
API_KEYS = [
    "YOUR_API_KEY_HERE"
]
active_key_index = 0

# 3. UNIFIED TRANSLATION ENGINE
def unified_translation(direction, target_lang, text_input, audio_path):
    global active_key_index
    print("\n--- [START TRANSLATION REQUEST] ---", flush=True)
    is_english_to_target = direction.startswith("English")

    source_lang = "English" if is_english_to_target else target_lang
    output_lang = target_lang if is_english_to_target else "English"
    safe_text = text_input if text_input else ""

    if not safe_text.strip() and not audio_path:
        print("[DEBUG] No text or audio provided.", flush=True)
        return safe_text, "Please provide text or record audio.", "", None, "", "", "", pd.DataFrame()

    prompt = f"""
    You are a linguistics and cultural expert in the {target_lang} language.
    I am providing an input in {source_lang}. It may be text, or an attached audio file.

    1. If an audio file is attached, transcribe exactly what was spoken in {source_lang}. If it's just text, use the text.
    2. Translate the {source_lang} input into {output_lang}.
    3. Break down the grammar, syntax, and cultural context.

    Input Text (if any): "{safe_text}"

    Respond ONLY with a valid JSON object in the exact following format:
    {{
        "transcription": "The exact text of what was said/inputted in the {source_lang} script",
        "translated_text": "The final translation in the {output_lang} script",
        "translit": "The phonetic pronunciation using English letters",
        "grammar": "A short explanation of the grammar rules applied.",
        "structure": "The sentence pattern (e.g., SOV or SVO)",
        "culture": "A 1-sentence note on how this phrase is used culturally in the region.",
        "breakdown": [["Morpheme 1", "Meaning 1"], ["Morpheme 2", "Meaning 2"]]
    }}
    """

    try:
        contents = [prompt]
        if audio_path and os.path.exists(audio_path):
            print(f"[DEBUG] Reading audio file from: {audio_path}", flush=True)
            audio_bytes = pathlib.Path(audio_path).read_bytes()
            if len(audio_bytes) > 0:
                contents.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"))

        response = None

        while active_key_index < len(API_KEYS):
            current_key = API_KEYS[active_key_index]

            if "PASTE_" in current_key:
                active_key_index += 1
                continue

            client = genai.Client(api_key=current_key)
            print(f"[DEBUG] Processing with Key #{active_key_index + 1}...", flush=True)

            try:
                max_retries = 3
                for attempt in range(max_retries):
                    model_to_use = 'gemini-3.6-flash' if attempt < 2 else 'gemini-3.7-flash'
                    print(f"        -> Attempt {attempt + 1}: Using {model_to_use}...", flush=True)

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            client.models.generate_content,
                            model=model_to_use,
                            contents=contents,
                            config=types.GenerateContentConfig(response_mime_type="application/json")
                        )
                        try:
                            response = future.result(timeout=60)
                            break
                        except concurrent.futures.TimeoutError:
                            print(f"[WARN] 60-second timeout reached on {model_to_use}.", flush=True)
                            if attempt == max_retries - 1: raise Exception("Request timed out after 60 seconds.")
                        except Exception as api_err:
                            err_str = str(api_err)
                            if "503" in err_str and attempt < max_retries - 1:
                                print(f"[WARN] Overload error. Retrying...", flush=True)
                                time.sleep(2)
                            else:
                                raise api_err

                if response:
                    break

            except Exception as e:
                err_str = str(e)
                if "429" in err_str:
                    print(f"[WARN] Key #{active_key_index + 1} Quota Exhausted! Swapping to next key...", flush=True)
                    active_key_index += 1
                    if active_key_index >= len(API_KEYS):
                        raise Exception("API Quota Exceeded on ALL provided keys.")
                elif "404" in err_str:
                     print(f"[WARN] Model deprecated. Passing error...", flush=True)
                     raise e
                else:
                    raise e

        if not response:
            raise Exception("No valid API keys available.")

        print("[DEBUG] Received response from Gemini. Parsing JSON...", flush=True)
        raw_response = response.text.strip()
        data = json.loads(raw_response)

        out_audio = None
        try:
            translit_text = data.get('translit', '').strip()
            if translit_text:
                print("[DEBUG] Generating phonetic TTS...", flush=True)
                tts = gTTS(text=translit_text, lang='hi')
                out_audio = "temp_audio.mp3"
                tts.save(out_audio)
        except Exception as tts_err:
            print(f"[WARN] TTS generation failed: {tts_err}", flush=True)
            out_audio = None

        df_data = data.get('breakdown', [])
        if not df_data: df_data = [["No data", "No data"]]
        df = pd.DataFrame(df_data, columns=["Morpheme", "English Meaning"])

        print("--- [REQUEST COMPLETED SUCCESSFULLY] ---\n", flush=True)
        return (
            data.get('transcription', safe_text),
            data.get('translated_text', ''),
            data.get('translit', ''),
            out_audio,
            data.get('structure', ''),
            data.get('grammar', ''),
            data.get('culture', ''),
            df
        )

    except Exception as e:
        error_msg = f"Translation Error: {str(e)}"
        print(f"[ERROR] {error_msg}", flush=True)
        error_df = pd.DataFrame([["Error", error_msg]], columns=["Morpheme", "English Meaning"])
        return safe_text, error_msg, "Error", None, "Error", "Error", "Error", error_df

# 4. INSTANT UI FEEDBACK FUNCTION
def show_thinking():
    empty_df = pd.DataFrame([["...", "..."]], columns=["Morpheme", "English Meaning"])
    return (
        gr.update(),
        gr.update(value="[ PROCESSING... ]"),
        gr.update(value="..."),
        None,
        gr.update(value="..."),
        gr.update(value="..."),
        gr.update(value="..."),
        empty_df
    )

def update_direction_choices(lang):
    choices = [f"English to {lang}", f"{lang} to English"]
    return gr.update(choices=choices, value=f"English to {lang}")

# 5. DEFINE LINGUANE AI THEME & CSS
linguaNE_theme = gr.themes.Base(
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"],
).set(
    body_background_fill="#0B1120",
    body_background_fill_dark="#0B1120",
    body_text_color="#F8FAFC",
    body_text_color_dark="#F8FAFC",
    background_fill_primary="#111827",
    background_fill_primary_dark="#111827",
    background_fill_secondary="#0F172A",
    background_fill_secondary_dark="#0F172A",
    border_color_primary="#1E293B",
    border_color_primary_dark="#1E293B",
    block_background_fill="#111827",
    block_background_fill_dark="#111827",
    block_border_color="#1E293B",
    block_border_width="1px",
    block_label_text_color="#94A3B8",
    block_label_text_size="10px",
    block_title_text_color="#F8FAFC",
    input_background_fill="#0B1120",
    input_background_fill_dark="#0B1120",
    button_primary_background_fill="#14B8A6",
    button_primary_background_fill_dark="#14B8A6",
    button_primary_background_fill_hover="#0D9488",
    button_primary_background_fill_hover_dark="#0D9488",
    button_primary_text_color="#0B1120",
    button_primary_text_color_dark="#0B1120",
    color_accent_soft="#14B8A6",
    color_accent_soft_dark="#14B8A6",
    border_color_accent="#14B8A6",
    border_color_accent_dark="#14B8A6",
)

linguane_css = """
/* Core Dark Theme Forces */
body, .gradio-container { background-color: #0B1120 !important; color: #F8FAFC !important; }

/* Dashboard Typographic Styling */
.gr-block > label span { text-transform: uppercase !important; letter-spacing: 2px !important; color: #14B8A6 !important; font-size: 10px !important; font-family: 'JetBrains Mono', monospace !important; }
.textarea-container textarea, .gr-input { font-family: 'JetBrains Mono', monospace !important; color: #F8FAFC !important; font-size: 13px !important; }

/* Primary CTA Styling */
button.primary { box-shadow: 0 0 10px rgba(20, 184, 166, 0.15) !important; text-transform: uppercase !important; letter-spacing: 2px !important; font-size: 12px !important; font-weight: 600 !important; border-radius: 4px !important; transition: all 0.3s ease !important; }
button.primary:hover { box-shadow: 0 0 15px rgba(20, 184, 166, 0.4) !important; border-color: #14B8A6 !important; }

/* Structural Grid & Cards */
.gr-box, .gr-panel { border-radius: 4px !important; border: 1px solid #1E293B !important; }

/* Dataframe/Table Technical Aesthetics */
th { background-color: #0F172A !important; color: #14B8A6 !important; text-transform: uppercase !important; font-size: 10px !important; font-family: 'JetBrains Mono', monospace !important; letter-spacing: 1px !important; border-bottom: 1px solid #1E293B !important;}
td { background-color: #111827 !important; border-color: #1E293B !important; color: #94A3B8 !important; font-family: 'JetBrains Mono', monospace !important; font-size: 12px !important; }

/* Audio Waveform UI Restyle */
.audio-container { background: transparent !important; border: 1px solid #1E293B !important; }
.record-button { background-color: #0B1120 !important; color: #14B8A6 !important; border: 1px solid #1E293B !important; }
.record-button.recording { color: #14B8A6 !important; border-color: #14B8A6 !important; box-shadow: 0 0 10px rgba(20, 184, 166, 0.3) !important; }
"""

# 6. BUILD USER INTERFACE (Removed theme/css from Blocks)
with gr.Blocks() as demo:

    # Header Section
    gr.HTML("""
    <div style="border-bottom: 1px solid #1E293B; padding-bottom: 20px; margin-bottom: 30px;">
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #14B8A6; letter-spacing: 2px; text-transform: uppercase;">LINGUANE / AI LANGUAGE ENGINE</div>
        <h1 style="color: #F8FAFC; margin-top: 8px; margin-bottom: 4px; font-weight: 700; font-size: 32px; font-family: 'Inter', sans-serif; letter-spacing: -0.5px;">LinguaNE</h1>
        <p style="color: #94A3B8; font-size: 15px; font-weight: 400; margin: 0; font-family: 'Inter', sans-serif;">The Bodo Linguistic Engine</p>
    </div>
    """)

    with gr.Row():
        target_language = gr.Dropdown(
            choices=["Bodo", "Assamese", "Khasi", "Mizo", "Garo", "Manipuri (Meitei)"],
            value="Bodo", label="TARGET LANGUAGE", interactive=True
        )
        direction_dropdown = gr.Dropdown(
            choices=["English to Bodo", "Bodo to English"],
            value="English to Bodo", label="TRANSLATION DIRECTION", interactive=True
        )

    gr.HTML("""<div style="font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #94A3B8; letter-spacing: 2px; margin-top: 20px; margin-bottom: -10px; text-transform: uppercase;">MULTIMODAL AI / VOICE INPUT</div>""")
    with gr.Row():
        audio_in = gr.Audio(sources=["microphone"], type="filepath", label="RAW AUDIO CAPTURE")
        text_in = gr.Textbox(label="TEXT INPUT PROTOCOL", placeholder="Enter sentence here...")

    submit_btn = gr.Button("INITIALIZE TRANSLATION ENGINE", variant="primary")

    gr.HTML("""<div style="height: 1px; background-color: #1E293B; margin: 30px 0;"></div>""")

    with gr.Row():
        with gr.Column():
            gr.HTML("""<div style="font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #94A3B8; letter-spacing: 2px; margin-bottom: 5px; text-transform: uppercase;">LANGUAGE PRESERVATION DATA</div>""")
            translation_out = gr.Textbox(label="TRANSLATED PAYLOAD", lines=2)
            phonetics_out = gr.Textbox(label="ROMAN TRANSLITERATION", lines=2)
            audio_out = gr.Audio(label="SYNTHESIZED PRONUNCIATION")

        with gr.Column():
            gr.HTML("""<div style="font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #94A3B8; letter-spacing: 2px; margin-bottom: 5px; text-transform: uppercase;">CULTURAL INTELLIGENCE & SYNTAX</div>""")
            struct_out = gr.Textbox(label="SYNTAX STRUCTURE")
            gram_out = gr.Textbox(label="GRAMMATICAL LOGIC")
            cult_out = gr.Textbox(label="CULTURAL CONTEXT", lines=2)

    gr.HTML("""<div style="font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #94A3B8; letter-spacing: 2px; margin-top: 20px; margin-bottom: -10px; text-transform: uppercase;">MORPHOLOGY BREAKDOWN</div>""")
    with gr.Row():
        df_out = gr.Dataframe(headers=["Morpheme", "Linguistic Meaning"])

    # Event Bindings
    target_language.change(fn=update_direction_choices, inputs=[target_language], outputs=[direction_dropdown])

    submit_btn.click(
        fn=show_thinking,
        inputs=[],
        outputs=[text_in, translation_out, phonetics_out, audio_out, struct_out, gram_out, cult_out, df_out]
    ).then(
        fn=unified_translation,
        inputs=[direction_dropdown, target_language, text_in, audio_in],
        outputs=[text_in, translation_out, phonetics_out, audio_out, struct_out, gram_out, cult_out, df_out]
    )

# 7. LAUNCH LOCAL GRADIO SERVER (Theme & CSS passed here)
demo.launch(share=False, server_port=7860, prevent_thread_lock=True, theme=linguaNE_theme, css=linguane_css)

# 8. DOWNLOAD & START CLOUDFLARE TUNNEL
if not os.path.exists("cloudflared"):
    print("Downloading Cloudflare Tunnel binary...", flush=True)
    subprocess.run(["wget", "-q", "-nc", "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", "-O", "cloudflared"])
    subprocess.run(["chmod", "+x", "cloudflared"])

subprocess.run(["pkill", "-f", "cloudflared"])
os.system("./cloudflared tunnel --url http://127.0.0.1:7860 > cloudflare.log 2>&1 &")

print("Generating secure public link...", flush=True)
live_link = None
for _ in range(25):
    time.sleep(1)
    if os.path.exists("cloudflare.log"):
        with open("cloudflare.log", "r") as f:
            log_content = f.read()
        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", log_content)
        if match:
            live_link = match.group(0)
            break

if live_link:
    print("\n" + "="*60, flush=True)
    print(f"🌟 CLICK THIS URL FOR YOUR DEMO:\n{live_link}", flush=True)
    print("="*60 + "\n", flush=True)
else:
    print("\nTunnel setup timed out. Check cloudflare.log for details.", flush=True)
