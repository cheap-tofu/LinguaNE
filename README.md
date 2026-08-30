
# LinguaNE: The Bodo Linguistic Engine 🌐

**Multimodal AI translation and linguistic mapping for under-resourced indigenous languages of Northeast India.**

LinguaNE bypasses legacy statistical machine translation and traditional Speech-to-Text (STT) bottlenecks. By injecting raw audio directly into a multimodal AI brain, the platform performs deep morphological mapping, structural syntax breakdown, and cultural context extraction for languages facing digital extinction. 

Built initially as a robust proof-of-concept for **Bodo**, the architecture scales instantly to Assamese, Khasi, Mizo, Garo, and Manipuri with zero codebase alterations.

## ✨ Core Innovations

* **Direct Multimodal Injection:** Eliminates the hallucination loop of legacy STT engines by allowing the AI to process raw native voice bytes directly.
* **Deep Linguistic Mapping:** Outputs forced JSON structures breaking down sentences into isolated morphemes, grammar logic, and SVO/SOV syntax patterns.
* **Cultural Intelligence:** Maps cultural nuances and regional context alongside direct translations.
* **Phonetic Accessibility:** Generates on-the-fly Roman transliterations and synthesizes localized audio pronunciations.

## 🛠️ Technical Architecture & Resilience

LinguaNE is engineered to survive the hostile networking environments of hackathons and rural deployments:

* **Engine:** Google Gemini (3.6/3.7 Flash) via the modern `genai` SDK.
* **Interface:** Gradio 6.0 featuring a custom `JetBrains Mono` and `Inter` dark-theme UI.
* **Failover Protocol:** 
  * **Auto-Key Rotation Pool:** Silently swaps API credentials in the background if a `429 Quota Exhausted` error is triggered.
  * **ThreadPool Execution:** Implements strict 60-second timeouts to prevent UI hangs.
  * **503 Interception:** Automatically retries and reroutes requests during server overloads.
* **Deployment:** Integrated Cloudflare Tunneling bypasses local firewalls to generate secure, shareable public links instantly.

## 🚀 Quick Start

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/YOUR_USERNAME/LinguaNE.git](https://github.com/YOUR_USERNAME/LinguaNE.git)
   cd LinguaNE

2. **Install dependencies:**
   ```bash
   pip install -U gradio gtts pandas google-genai SpeechRecognition

3. **Configure API Keys:**
   Open the main Python file and insert your Google AI Studio keys into the `API_KEYS` pool.

4. **Launch the engine:**
   ```bash
   python main.py

*The application will automatically spin up a local Gradio server and initialize a Cloudflare tunnel for external access.*











