"""
GitHub Push Helper
実行のたびにPersonal Access Tokenをその場で(非表示で)入力させ、pushする。
push後はremote URLからトークンを自動的に削除するので、履歴やnotebookに
トークンの平文が残らない。
"""
import subprocess
from pathlib import Path
from getpass import getpass

ROOT = Path(__file__).resolve().parents[2]
GITHUB_USERNAME = "mizuya26-collab"
REPO = "Kgo"


def run(cmd, cwd=ROOT):
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def github_push(branch: str = "main"):
    token = getpass("GitHub Personal Access Token を入力してください(画面には表示されません): ").strip()
    if not token:
        print("[中止] トークンが空です。")
        return

    remote_url = f"https://{GITHUB_USERNAME}:{token}@github.com/{GITHUB_USERNAME}/{REPO}.git"

    rc, out, err = run(f"git remote set-url origin {remote_url}")
    if rc != 0:
        print(f"[FAIL] remote set-url: {err}")
        return

    rc, out, err = run(f"git push origin {branch}")
    print(out)
    if rc != 0:
        print(f"[FAIL] push: {err}")
    else:
        print("[OK] push成功")

    run(f"git remote set-url origin https://github.com/{GITHUB_USERNAME}/{REPO}.git")
    print("(remote URLからトークンを削除しました)")


if __name__ == "__main__":
    github_push()
