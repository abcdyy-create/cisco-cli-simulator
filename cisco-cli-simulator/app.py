from flask import Flask, render_template, request, jsonify, session
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

LEVELS = [
    {
        "id": 1,
        "title": "Interface Down",
        "brief": "PC-A から Router R1 の Gi0/1 側ネットワークへ通信できません。R1 の該当インターフェースを復旧してください。",
        "start": {"hostname": "R1", "mode": "user", "interfaces": {"GigabitEthernet0/1": {"ip": None, "mask": None, "up": False}}},
        "answer": ["interface gigabitethernet0/1", "interface gi0/1", "ip address 192.168.10.1 255.255.255.0", "no shutdown"],
        "goal": "Gi0/1 に 192.168.10.1/24 を設定し、no shutdown する。",
    },
    {
        "id": 2,
        "title": "VLAN Trouble",
        "brief": "SW1 の PC-A ポートが正しい VLAN に入っていません。Fa0/3 を VLAN 20 の access port にしてください。",
        "start": {"hostname": "SW1", "mode": "user", "interfaces": {"FastEthernet0/3": {"vlan": 1, "mode": "dynamic"}}},
        "answer": ["interface fastethernet0/3", "interface fa0/3", "switchport mode access", "switchport access vlan 20"],
        "goal": "Fa0/3 を access mode、VLAN 20 にする。",
    },
    {
        "id": 3,
        "title": "Static Route",
        "brief": "R1 から 10.20.0.0/24 へ到達できません。隣の R2 は 192.168.1.2 です。R1 に静的ルートを追加してください。",
        "start": {"hostname": "R1", "mode": "user", "routes": []},
        "answer": ["ip route 10.20.0.0 255.255.255.0 192.168.1.2"],
        "goal": "10.20.0.0/24 を 192.168.1.2 経由で追加する。",
    },
    {
        "id": 4,
        "title": "OSPF Neighbor",
        "brief": "R1 と R2 が OSPF ネイバーになりません。R1 の OSPF process 1 に 192.168.10.0/24 を area 0 として追加してください。",
        "start": {"hostname": "R1", "mode": "user", "ospf": {"process": None, "networks": []}},
        "answer": ["router ospf 1", "network 192.168.10.0 0.0.0.255 area 0"],
        "goal": "OSPF process 1 を起動し、192.168.10.0/24 を area 0 に参加させる。",
    },
    {
        "id": 5,
        "title": "ACL Block",
        "brief": "管理用 PC (192.168.50.10) から Web Server (10.10.10.10) に HTTPS 接続できるようにしてください。ACL 101 に HTTPS を許可する行を追加します。",
        "start": {"hostname": "R1", "mode": "user", "acl": []},
        "answer": ["access-list 101 permit tcp host 192.168.50.10 host 10.10.10.10 eq 443"],
        "goal": "指定の送信元から指定サーバーへの TCP/443 を許可する。",
    },
]

def fresh_state(level):
    import copy
    return copy.deepcopy(level["start"])

@app.route("/")
def index():
    if "level" not in session:
        session["level"] = 1
    return render_template("index.html")

@app.route("/api/start", methods=["POST"])
def start():
    level_id = int(request.json.get("level", 1))
    level = next((x for x in LEVELS if x["id"] == level_id), LEVELS[0])
    session["level"] = level_id
    session["state"] = fresh_state(level)
    return jsonify(level=level, state=session["state"])

@app.route("/api/reset", methods=["POST"])
def reset():
    level_id = int(session.get("level", 1))
    level = next(x for x in LEVELS if x["id"] == level_id)
    session["state"] = fresh_state(level)
    return jsonify(level=level, state=session["state"])

def normalize(s):
    return " ".join(s.strip().lower().split())

def prompt(state):
    mode = state.get("mode", "user")
    h = state.get("hostname", "R1")
    if mode == "user": return f"{h}>"
    if mode == "priv": return f"{h}#"
    if mode == "config": return f"{h}(config)#"
    if mode == "config-if": return f"{h}(config-if)#"
    if mode == "config-router": return f"{h}(config-router)#"
    if mode == "config-acl": return f"{h}(config-ext-nacl)#"
    return f"{h}>"

def execute(cmd, state):
    c = normalize(cmd)
    out = []
    new = dict(state)
    mode = state.get("mode", "user")

    if not c:
        return "", new

    if c in ("enable", "en") and mode == "user":
        new["mode"] = "priv"
        return "", new
    if c in ("disable",) and mode == "priv":
        new["mode"] = "user"
        return "", new
    if c in ("configure terminal", "conf t") and mode == "priv":
        new["mode"] = "config"
        return "Enter configuration commands, one per line. End with CNTL/Z.", new
    if c in ("end", "exit") and mode in ("config", "config-if", "config-router", "config-acl"):
        new["mode"] = "priv" if c == "end" or mode == "config" else "config"
        return "", new

    if c in ("show running-config", "show run") and mode == "priv":
        out.append("Building configuration...")
        out.append(f"hostname {state.get('hostname','R1')}")
        for name, itf in state.get("interfaces", {}).items():
            out.append(f"interface {name}")
            if itf.get("ip"):
                out.append(f" ip address {itf['ip']} {itf['mask']}")
            if itf.get("vlan") is not None:
                out.append(f" switchport access vlan {itf['vlan']}")
            if itf.get("mode") == "access":
                out.append(" switchport mode access")
            if itf.get("up"):
                out.append(" no shutdown")
        for route in state.get("routes", []):
            out.append(f"ip route {route}")
        if state.get("ospf", {}).get("process"):
            out.append(f"router ospf {state['ospf']['process']}")
            for n in state["ospf"]["networks"]:
                out.append(f" network {n}")
        for a in state.get("acl", []):
            out.append(f"access-list 101 {a}")
        return "\n".join(out), new

    if c == "show ip interface brief" and mode == "priv":
        out.append("Interface              IP-Address      Status    Protocol")
        for name, itf in state.get("interfaces", {}).items():
            ip = itf.get("ip") or "unassigned"
            status = "up" if itf.get("up") else "administratively down"
            proto = "up" if itf.get("up") else "down"
            out.append(f"{name:<23}{ip:<16}{status:<10}{proto}")
        return "\n".join(out), new

    # Configuration commands
    if mode == "config" and c.startswith("interface "):
        arg = c[10:].strip()
        aliases = {"gi0/1": "GigabitEthernet0/1", "gigabitethernet0/1": "GigabitEthernet0/1",
                   "fa0/3": "FastEthernet0/3", "fastethernet0/3": "FastEthernet0/3"}
        name = aliases.get(arg, arg)
        new.setdefault("interfaces", {}).setdefault(name, {})
        new["current_interface"] = name
        new["mode"] = "config-if"
        return "", new

    if mode == "config" and c.startswith("router ospf "):
        pid = c.split()[-1]
        new.setdefault("ospf", {})["process"] = pid
        new["mode"] = "config-router"
        return "", new

    if mode == "config" and c.startswith("access-list 101 "):
        rest = cmd.strip()[15:].strip()
        new.setdefault("acl", []).append(rest)
        return "", new

    if mode == "config-if":
        name = new.get("current_interface")
        itf = new["interfaces"][name]
        if c.startswith("ip address "):
            parts = cmd.strip().split()
            if len(parts) == 4:
                itf["ip"], itf["mask"] = parts[2], parts[3]
                return "", new
        if c == "no shutdown":
            itf["up"] = True
            return "Interface is up.", new
        if c == "shutdown":
            itf["up"] = False
            return "", new
        if c == "switchport mode access":
            itf["mode"] = "access"
            return "", new
        if c.startswith("switchport access vlan "):
            itf["vlan"] = int(c.split()[-1])
            return "", new

    if mode == "config-router" and c.startswith("network "):
        rest = cmd.strip()[8:].strip()
        new.setdefault("ospf", {}).setdefault("networks", []).append(rest)
        return "", new

    if mode == "config" and c.startswith("ip route "):
        rest = cmd.strip()[9:].strip()
        new.setdefault("routes", []).append(rest)
        return "", new

    if c.startswith("ping ") and mode == "priv":
        target = c[5:].strip()
        return f"Type escape sequence to abort.\nSending 5, 100-byte ICMP Echos to {target}, timeout is 2 seconds:\n!!!!!\nSuccess rate is 100 percent (5/5)", new

    return f"% Invalid input detected at '^' marker.\n{prompt(state)} {cmd}", new

def check(level, state):
    if level == 1:
        i = state["interfaces"].get("GigabitEthernet0/1", {})
        return i.get("ip") == "192.168.10.1" and i.get("mask") == "255.255.255.0" and i.get("up") is True
    if level == 2:
        i = state["interfaces"].get("FastEthernet0/3", {})
        return i.get("vlan") == 20 and i.get("mode") == "access"
    if level == 3:
        return "10.20.0.0 255.255.255.0 192.168.1.2" in state.get("routes", [])
    if level == 4:
        return state.get("ospf", {}).get("process") == "1" and any(
            x == "192.168.10.0 0.0.0.255 area 0" for x in state.get("ospf", {}).get("networks", [])
        )
    if level == 5:
        return any(normalize(x) == "permit tcp host 192.168.50.10 host 10.10.10.10 eq 443" for x in state.get("acl", []))
    return False

@app.route("/api/command", methods=["POST"])
def command():
    cmd = request.json.get("command", "")
    level_id = int(session.get("level", 1))
    level = next(x for x in LEVELS if x["id"] == level_id)
    state = session.get("state", fresh_state(level))
    output, state = execute(cmd, state)
    solved = check(level_id, state)
    session["state"] = state
    return jsonify(output=output, prompt=prompt(state), solved=solved)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
