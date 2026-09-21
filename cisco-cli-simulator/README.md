# NETOPS Cisco Incident Simulator v4

10問を「提示情報だけで原因を論理的に切り分けられる」設計に作り直した版です。

各問題には:
- 障害申告
- 正常時の設計情報
- 専用ネットワーク構成図
- 調査用showコマンド
- 段階ヒント
- 復旧判定
があります。

既存GitHubリポジトリの中身をこのZIPの中身で置換してpushしてください。
Renderは既存設定の `pip install -r requirements.txt` / `gunicorn app:app` のままで動きます。
