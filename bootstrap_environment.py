#!/usr/bin/env python3
"""
Bootstrap script — Claude Code + Ollama(gpt-oss:20b) 動作環境の再構築
2026-08-29 に動作確認済みの手順・設定値をそのまま反映しています。
詳細な検証結果は self_evolution/state/verified_environment.json を参照。
 
使い方(Colab):
    exec(open("/content/gpt_oss_proxy_test/bootstrap_environment.py").read())
"""
 
import os
import subprocess
import time
import urllib.request
 
def run(cmd, timeout=None):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
 
 
def ask(prompt: str) -> bool:
    return input(f"{prompt} (yes/NO): ").strip().lower() == "yes"
 
 
print("=" * 70)
print("BOOTSTRAP: Claude Code + Ollama(gpt-oss:20b) 環境構築")
print("=" * 70)
 
# --- GPU確認(最優先) ---
gpu_check = run("nvidia-smi")
if gpu_check.returncode != 0:
    raise RuntimeError(
        "GPUが検出できません。ランタイム -> ランタイムのタイプを変更 -> T4 GPU を選択してから再実行してください。"
    )
print("[OK] GPU検出成功")
 
# --- zstd ---
if run("which zstd").returncode != 0:
    if ask("zstdをインストールしますか？"):
        run("apt-get update -qq && apt-get install -y -qq zstd")
 
# --- GPU検出ツール(Ollamaより先にインストールすること!) ---
if run("which lspci").returncode != 0:
    if ask("pciutils/lshw(GPU検出用)をインストールしますか？"):
        run("apt-get install -y -qq pciutils lshw")
 
# --- Ollama本体 ---
if run("which ollama").returncode != 0:
    if ask("Ollama本体をインストールしますか？"):
        proc = run("curl -fsSL https://ollama.com/install.sh | sh")
        print(proc.stdout[-500:])
        if "Unable to detect NVIDIA" in proc.stdout:
            print("[警告] GPU未検出のまま進んでいます。pciutils/lshwが先に入っているか確認してください。")
 
# --- Ollama起動(コンテキスト長を必ず指定) ---
already_up = False
try:
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as resp:
        already_up = resp.status == 200
except Exception:
    already_up = False
 
if not already_up:
    env = os.environ.copy()
    env["OLLAMA_CONTEXT_LENGTH"] = "16384"
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    time.sleep(8)
    print("[OK] Ollama起動(OLLAMA_CONTEXT_LENGTH=16384)")
else:
    print("[OK] Ollamaは既に起動済みです(コンテキスト長は起動時の設定のままです)")
 
# --- gpt-oss:20b モデル ---
if "gpt-oss:20b" not in run("ollama list").stdout:
    if ask("gpt-oss:20bモデルをダウンロードしますか？(数分かかります)"):
        run("ollama pull gpt-oss:20b", timeout=1800)
 
# --- Claude Code ---
if run("which claude").returncode != 0:
    if ask("Claude Codeをインストールしますか？"):
        run("curl -fsSL https://claude.ai/install.sh | bash")
    local_bin = os.path.expanduser("~/.local/bin")
    if local_bin not in os.environ["PATH"]:
        os.environ["PATH"] = local_bin + ":" + os.environ["PATH"]
 
# --- Claude Code実行用の環境変数を設定 ---
os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:11434"
os.environ["ANTHROPIC_AUTH_TOKEN"] = "ollama"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT"] = "1"
 
print("\n" + "=" * 70)
print("BOOTSTRAP COMPLETE")
print("=" * 70)
print("Claude Codeを使う際は、以下のように --model を明示してください:")
print('  claude -p --model gpt-oss:20b "あなたの指示"')
print("\n注意: gpt-oss:20bの初回ロードには1〜2分かかります。")
