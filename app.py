from flask import Flask, request, jsonify
import logging
import os
from functools import wraps
import unicodedata # NFKC正規化のために必要

# Sudachiライブラリ
import sudachipy
from sudachipy import tokenizer
from sudachipy import dictionary

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- Sudachi 初期化 ---
try:
    # sudachidict_full をロード
    SUD_TOKENIZER = dictionary.Dictionary(dict="full").create()
    logging.info("Sudachi dictionary (full) loaded successfully.")
except Exception as e:
    logging.error(f"Failed to initialize Sudachi (full): {e}")
    logging.error("Ensure sudachipy and sudachidict_full are installed.")
    SUD_TOKENIZER = None

# --- 認証機能 (変更なし) ---
SECRET_API_KEY = os.environ.get("FURIGANA_API_KEY")

if not SECRET_API_KEY:
    logging.warning("!!! FURIGANA_API_KEY is not set. Authentication is disabled. !!!")

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not SECRET_API_KEY:
            return f(*args, **kwargs)
        provided_key = request.headers.get('X-API-KEY')
        if not provided_key or provided_key != SECRET_API_KEY:
            return jsonify({"error": "Unauthorized. Invalid or missing API key."}), 401
        return f(*args, **kwargs)
    return decorated_function
# --- 認証機能ここまで ---


@app.route('/')
def health_check():
    """ヘルスチェック用"""
    return "Sudachi Morpheme API server (Full) is running!"

@app.route('/get_morphemes', methods=['POST']) # ★ エンドポイント名を変更
@require_api_key
def handle_get_morphemes():
    """
    Sudachiの形態素解析結果をそのまま返すAPI
    JSON Payload:
    {
        "text": "解析したい文字列",
        "mode": "A" or "B" or "C" (optional, default: "C")
    }
    """
    if not SUD_TOKENIZER:
        return jsonify({"error": "Sudachi tokenizer is not initialized."}), 503

    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "No 'text' key in JSON payload"}), 400

        text = data['text']
        mode_str = data.get('mode', 'C').upper()

        if mode_str not in ['A', 'B', 'C']:
             return jsonify({"error": "Invalid 'mode'. Must be 'A', 'B', or 'C'."}), 400
        
        # --- ★ 処理の変更ここから ★ ---

        # 1. NFKC正規化 (入力前の下ごしらえ)
        normalized_text = unicodedata.normalize('NFKC', text)
        
        # 2. Sudachiのモード設定
        if mode_str == 'A':
            mode = tokenizer.Tokenizer.SplitMode.A
        elif mode_str == 'B':
            mode = tokenizer.Tokenizer.SplitMode.B
        else:
            mode = tokenizer.Tokenizer.SplitMode.C
            
        # 3. 形態素解析を実行
        morphemes = SUD_TOKENIZER.tokenize(normalized_text, mode)

        # 4. クライアントに返すための情報（辞書のリスト）を作成
        result_list = []
        for m in morphemes:
            result_list.append({
                "surface": m.surface(),             # 表層形 (例: "学ぶ")
                "reading": m.reading_form(),        # 読み (例: "マナブ") ※カタカナ
                "pos": m.part_of_speech(),          # 品詞 (例: ["動詞", ...])
                "normalized": m.normalized_form(),  # 正規形 (例: "学ぶ")
                # 必要なら他の情報も追加 (m.dictionary_form() など)
            })

        # 5. マッピング等を行わず、そのまま返す
        response = {
            "morphemes": result_list,
            "mode_used": mode_str
        }
        
        return jsonify(response), 200
        # --- ★ 処理の変更ここまで ★ ---

    except Exception as e:
        logging.error(f"Error in /get_morphemes: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {e}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)