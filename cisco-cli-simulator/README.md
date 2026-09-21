# NETOPS // Cisco Incident Simulator v2

Cisco IOS風CLIで障害を調査・復旧するブラウザゲーム。

## 今回のステージ
PC-AからWEB-SRVへ到達不能。答えは画面に表示されません。
`show`、`ping`などで調査して原因を特定します。

## 主な機能
- IOS風モード遷移
- `show run`, `show ip interface brief`, `show ip route`, `show interfaces`
- ping
- `?` ヘルプ
- Tab補完
- ↑↓ コマンド履歴
- `do show`
- ヒントとスコア
- ライブトポロジー
- Cisco風ログ
- Render対応

## Render
Build: `pip install -r requirements.txt`
Start: `gunicorn app:app`

既存GitHubリポジトリのファイルをこのZIPの中身で置き換えてpushすれば、自動デプロイできます。
