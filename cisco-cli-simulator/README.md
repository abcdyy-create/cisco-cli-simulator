# Cisco CLI Simulator

Python + Flask で作った、Cisco IOS風のコマンド入力ゲームです。

## ローカルで起動

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

ブラウザで http://127.0.0.1:5000/ を開きます。

## Renderで公開

1. このフォルダをGitHubリポジトリにpush
2. RenderでNew > Web Service
3. GitHubリポジトリを選択
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn app:app`
6. Freeプランで作成

`render.yaml` も入っているのでBlueprintとして読み込むこともできます。

## 今後追加できるもの

- コマンド履歴（↑↓）
- Tab補完
- 本物っぽいIOSエラー
- showコマンド増加
- VLAN/Trunk/STP
- OSPF/BGP
- NAT/DHCP/ACL
- スコア・タイムアタック
- ネットワーク構成図
- ランダム障害生成
