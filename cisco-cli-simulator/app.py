from flask import Flask, render_template, request, jsonify, session
import os, copy, time

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me")

BASE = {
    "hostname": "R1",
    "mode": "user",
    "current_interface": None,
    "interfaces": {
        "GigabitEthernet0/0": {"ip":"192.168.10.1","mask":"255.255.255.0","admin":True,"link":True,"desc":"LAN → SW1"},
        "GigabitEthernet0/1": {"ip":"10.0.12.1","mask":"255.255.255.252","admin":False,"link":True,"desc":"WAN → R2"},
    },
    "routes": [
        {"type":"C","net":"192.168.10.0/24","via":None,"interface":"GigabitEthernet0/0"},
    ],
    "saved": False,
    "commands": 0,
    "hints": 0,
    "started": 0,
}

MISSION = {
    "title":"THE SILENT UPLINK",
    "ticket":"INC-2048",
    "brief":"営業部のPC-Aから社内Webサーバーへアクセスできない。ユーザーから分かっているのは「朝から急につながらない」だけ。R1を調査し、原因を特定して通信を復旧せよ。",
    "pc":"192.168.10.20/24",
    "server":"10.20.0.10",
}

def fresh():
    s=copy.deepcopy(BASE); s["started"]=int(time.time()); return s

def norm(x): return " ".join(x.strip().lower().split())

def canonical_if(x):
    x=norm(x).replace(" ","")
    aliases={
        "gi0/0":"GigabitEthernet0/0","gig0/0":"GigabitEthernet0/0","gigabitethernet0/0":"GigabitEthernet0/0",
        "gi0/1":"GigabitEthernet0/1","gig0/1":"GigabitEthernet0/1","gigabitethernet0/1":"GigabitEthernet0/1",
    }
    return aliases.get(x)

def prompt(s):
    h=s["hostname"]; m=s["mode"]
    return {"user":f"{h}>","priv":f"{h}#","config":f"{h}(config)#","config-if":f"{h}(config-if)#"}[m]

def connected(s, name):
    i=s["interfaces"][name]
    return i["admin"] and i["link"]

def solved(s):
    return connected(s,"GigabitEthernet0/1")

def routes_text(s):
    rows=["Codes: C - connected, S - static", ""]
    for name,i in s["interfaces"].items():
        if connected(s,name):
            if name=="GigabitEthernet0/0": net="192.168.10.0/24"
            else: net="10.0.12.0/30"
            rows.append(f"C    {net} is directly connected, {name}")
    if solved(s):
        rows.append("S    10.20.0.0/24 [1/0] via 10.0.12.2")
    return "\n".join(rows)

def run_config(s):
    out=["Building configuration...","","Current configuration : 1042 bytes","!","version 15.9","service timestamps debug datetime msec","service timestamps log datetime msec","!",f"hostname {s['hostname']}","!"]
    for name,i in s["interfaces"].items():
        out += [f"interface {name}", f" description {i['desc']}", f" ip address {i['ip']} {i['mask']}"]
        if not i["admin"]: out.append(" shutdown")
        out.append("!")
    out += ["ip route 10.20.0.0 255.255.255.0 10.0.12.2","!","line con 0","line vty 0 4"," login","!","end"]
    return "\n".join(out)

HELP = {
"user":["enable","ping <ip>","show ?"],
"priv":["configure terminal","show running-config","show ip interface brief","show interfaces <interface>","show ip route","ping <ip>","copy running-config startup-config","disable"],
"config":["interface <interface>","hostname <name>","do show ...","end","exit"],
"config-if":["no shutdown","shutdown","description <text>","do show ...","end","exit"],
}

def help_text(s, prefix):
    cmds=HELP[s["mode"]]
    p=norm(prefix)
    hits=[c for c in cmds if norm(c).startswith(p)]
    return "\n".join(hits or cmds)

def execute(raw,s):
    c=norm(raw); mode=s["mode"]
    if not c: return ""

    if c.endswith("?"):
        return help_text(s,c[:-1].strip())

    # navigation
    if c in ("enable","en") and mode=="user": s["mode"]="priv"; return ""
    if c=="disable" and mode=="priv": s["mode"]="user"; return ""
    if c in ("configure terminal","conf t","conf ter") and mode=="priv":
        s["mode"]="config"; return "Enter configuration commands, one per line.  End with CNTL/Z."
    if c=="end" and mode in ("config","config-if"): s["mode"]="priv"; s["current_interface"]=None; return ""
    if c=="exit" and mode=="config-if": s["mode"]="config"; s["current_interface"]=None; return ""
    if c=="exit" and mode=="config": s["mode"]="priv"; return ""

    # do from config modes
    if c.startswith("do ") and mode in ("config","config-if"):
        old=s["mode"]; s["mode"]="priv"; out=execute(raw.strip()[3:],s); s["mode"]=old; return out

    # show
    if mode=="priv" and c in ("show ip interface brief","sh ip int br","sh ip int brief"):
        lines=["Interface              IP-Address      OK? Method Status                Protocol"]
        for name,i in s["interfaces"].items():
            status="up" if i["admin"] and i["link"] else ("administratively down" if not i["admin"] else "down")
            proto="up" if i["admin"] and i["link"] else "down"
            lines.append(f"{name:<23}{i['ip']:<16}YES manual {status:<21}{proto}")
        return "\n".join(lines)
    if mode=="priv" and c in ("show running-config","show run","sh run"):
        return run_config(s)
    if mode=="priv" and c in ("show ip route","sh ip route"):
        return routes_text(s)
    if mode=="priv" and (c.startswith("show interfaces ") or c.startswith("sh int ")):
        arg=raw.split(None,2)[-1]; name=canonical_if(arg)
        if not name: return "% Invalid interface"
        i=s["interfaces"][name]
        line="up" if i["admin"] and i["link"] else ("administratively down" if not i["admin"] else "down")
        proto="up" if i["admin"] and i["link"] else "down"
        return f"{name} is {line}, line protocol is {proto}\n  Description: {i['desc']}\n  Internet address is {i['ip']}/" + ("24" if i["mask"].endswith(".0") else "30") + "\n  MTU 1500 bytes, BW 1000000 Kbit/sec\n  5 minute input rate 0 bits/sec, 0 packets/sec\n  5 minute output rate 0 bits/sec, 0 packets/sec"

    # config
    if mode=="config" and c.startswith("interface "):
        name=canonical_if(raw.split(None,1)[1])
        if not name: return "% Invalid interface type and number"
        s["current_interface"]=name; s["mode"]="config-if"; return ""
    if mode=="config" and c.startswith("hostname "):
        s["hostname"]=raw.strip().split(None,1)[1]; return ""

    if mode=="config-if":
        name=s["current_interface"]; i=s["interfaces"][name]
        if c in ("no shutdown","no shut"):
            was=connected(s,name); i["admin"]=True
            if not was and i["link"]:
                return f"*LINK-3-UPDOWN: Interface {name}, changed state to up\n*LINEPROTO-5-UPDOWN: Line protocol on Interface {name}, changed state to up"
            return ""
        if c in ("shutdown","shut"):
            i["admin"]=False
            return f"*LINK-5-CHANGED: Interface {name}, changed state to administratively down"
        if c.startswith("description "):
            i["desc"]=raw.strip().split(None,1)[1]; return ""

    if mode=="priv" and c.startswith("ping "):
        target=c.split(None,1)[1]
        ok = target in ("192.168.10.20","192.168.10.1") or (solved(s) and target in ("10.0.12.2","10.20.0.10"))
        marks="!!!!!" if ok else "....."
        rate="100" if ok else "0"
        return f"Type escape sequence to abort.\nSending 5, 100-byte ICMP Echos to {target}, timeout is 2 seconds:\n{marks}\nSuccess rate is {rate} percent (5/5)" if ok else f"Type escape sequence to abort.\nSending 5, 100-byte ICMP Echos to {target}, timeout is 2 seconds:\n{marks}\nSuccess rate is {rate} percent (0/5)"
    if mode=="user" and c.startswith("ping "):
        target=c.split(None,1)[1]
        ok=target=="192.168.10.1" or (solved(s) and target=="10.20.0.10")
        return f"Type escape sequence to abort.\nSending 5, 100-byte ICMP Echos to {target}, timeout is 2 seconds:\n{'!!!!!' if ok else '.....'}\nSuccess rate is {'100 percent (5/5)' if ok else '0 percent (0/5)'}"
    if mode=="priv" and c in ("copy running-config startup-config","copy run start","wr","write memory"):
        s["saved"]=True
        return "Building configuration...\n[OK]"

    return "% Invalid input detected at '^' marker."

@app.route("/")
def index(): return render_template("index.html")

@app.post("/api/start")
def start():
    session["state"]=fresh()
    return jsonify(mission=MISSION,prompt="R1>",topology=topology(session["state"]))

def topology(s):
    return {"r1wan": "up" if connected(s,"GigabitEthernet0/1") else "down",
            "server": "reachable" if solved(s) else "unreachable"}

@app.post("/api/cmd")
def cmd():
    s=session.get("state") or fresh()
    raw=request.json.get("command","")
    s["commands"]+=1
    out=execute(raw,s)
    session["state"]=s
    score=max(100,1000-s["commands"]*12-s["hints"]*150)
    return jsonify(output=out,prompt=prompt(s),solved=solved(s),score=score,topology=topology(s))

@app.post("/api/hint")
def hint():
    s=session.get("state") or fresh(); s["hints"]+=1; session["state"]=s
    hints=[
        "まずはL3インターフェースの状態を一覧で確認してみよ。",
        "WAN側は Gi0/1。Status と Protocol に注目。",
        "administratively down は物理断とは意味がちゃうで。",
        "Gi0/1 の interface configuration mode で shutdown 状態を解除する。",
    ]
    return jsonify(hint=hints[min(s["hints"]-1,len(hints)-1)],hints=s["hints"])

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=True)
