"""テスト全体の前置き。

**Claude Code から pytest を打っても、ユーザーの端末から打っても、同じ結果になるようにする。**
Claude Code が打つコマンドには環境変数 CLAUDECODE が付き、`build.episodes_root()` はそれを見て
本物の回を使わずに止める（#221・案A'）。テストは本物の回に書かないように作ってあるので、
ここで印を外して、ふつうの端末と同じ条件にする（印があるときの動きは test_sandbox_root.py で見る）。
"""

import os

os.environ.pop("CLAUDECODE", None)
os.environ.pop("OKURADI_REAL", None)
os.environ.pop("OKURADI_EPISODES_DIR", None)
os.environ.pop("OKURADI_SETTINGS", None)
