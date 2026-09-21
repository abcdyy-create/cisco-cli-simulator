from flask import Flask, render_template, request, jsonify, session
import os, copy

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "netops-v4-dev-key")

MISSIONS = [
{
"id":1,"ticket":"INC-301","title":"SILENT UPLINK","device":"R1","type":"interface",
"brief":"営業部PCから社内Webサーバーへ到達できない。朝から突然発生。LAN内通信は正常。",
"spec":["PC-A: 192.168.10.20/24, GW 192.168.10.1","R1 Gi0/0: 192.168.10.1/24 → LAN","R1 Gi0/1: 10.0.12.1/30 → R2","R2: 10.0.12.2/30","正常時はGi0/0・Gi0/1ともUP"],
"topology":["PC-A|192.168.10.20","SW1|L2","R1|Gi0/0 .1 / Gi0/1 .1","R2|10.0.12.2","WEB|10.20.0.10"],
"state":{"admin":False},"hints":["show ip interface brief でL3 IFを一覧確認。","Gi0/1のStatusに注目。","Gi0/1で no shutdown。"]
},
{
"id":2,"ticket":"INC-302","title":"WRONG GATEWAY","device":"PC-A","type":"gateway",
"brief":"PC-Aは同一LANのNASには届くが、別セグメントのWebサーバーには届かない。",
"spec":["PC-A: 192.168.10.20/24","正しいDefault Gateway: 192.168.10.1","DNS: 192.168.10.53","NAS: 192.168.10.50","WEB: 10.20.0.10"],
"topology":["PC-A|192.168.10.20","SW1|LAN","R1|192.168.10.1","R2|WAN","WEB|10.20.0.10"],
"state":{"gateway":"192.168.10.254"},"hints":["ipconfig で端末設定を確認。","同一LANだけ通るならL3出口を疑う。","set gateway 192.168.10.1。"]
},
{
"id":3,"ticket":"INC-303","title":"VLAN DRIFT","device":"SW1","type":"vlan",
"brief":"経理PCだけ通信不能。同じSW1につながる営業PCは正常。",
"spec":["Fa0/2: SALES-PC / VLAN 10","Fa0/3: ACCOUNTING-PC / VLAN 20","VLAN 10 = SALES","VLAN 20 = ACCOUNTING","Gi0/24 = uplink"],
"topology":["SALES|Fa0/2 V10","SW1|Fa0/3 ?","UPLINK|Gi0/24","R1|Router","SERVER|Internal"],
"state":{"vlan":10},"hints":["show vlan brief でポート所属を確認。","Fa0/3のVLANと仕様書を比較。","Fa0/3をaccess VLAN 20へ。"]
},
{
"id":4,"ticket":"INC-304","title":"TRUNK LOST","device":"SW1","type":"trunk",
"brief":"SW1側VLAN10端末からSW2側VLAN10端末へ届かない。各スイッチ内の同一VLAN通信は正常。",
"spec":["SW1 Gi0/24 ↔ SW2 Gi0/24","スイッチ間リンクは802.1Q trunk","Native VLAN 1","VLAN 10,20を運ぶ","物理リンクはUP"],
"topology":["PC-A|VLAN10","SW1|Gi0/24","SW2|Gi0/24","PC-B|VLAN10","—|—"],
"state":{"trunk":False},"hints":["show interfaces trunk。","Gi0/24のStatusを仕様と比較。","Gi0/24を switchport mode trunk。"]
},
{
"id":5,"ticket":"INC-305","title":"MISSING ROUTE","device":"R1","type":"route",
"brief":"本社LANから支社LAN 10.30.0.0/24へ到達不能。R1-R2間の直接接続は疎通する。",
"spec":["本社LAN: 192.168.10.0/24","R1 Gi0/1: 10.0.12.1/30","R2 Gi0/1: 10.0.12.2/30","支社LAN: 10.30.0.0/24","R1は支社LANをnext-hop 10.0.12.2へ送る設計"],
"topology":["HQ|192.168.10.0/24","R1|10.0.12.1","R2|10.0.12.2","BRANCH|10.30.0.0/24","SRV|10.30.0.10"],
"state":{"route":False},"hints":["show ip route。","10.30.0.0/24の経路があるか確認。","ip route 10.30.0.0 255.255.255.0 10.0.12.2。"]
},
{
"id":6,"ticket":"INC-306","title":"OSPF SILENCE","device":"R1","type":"ospf",
"brief":"R1-R2の物理リンクはUP。OSPFで学習するはずの10.40.0.0/24がR1に現れない。",
"spec":["OSPF Process ID: 1","R1-R2: 10.0.12.0/30","R1 Gi0/1: 10.0.12.1","R2 Gi0/1: 10.0.12.2","R1-R2リンクはArea 0"],
"topology":["LAN|192.168.10.0","R1|10.0.12.1","R2|10.0.12.2","OSPF|AREA 0","REMOTE|10.40.0.0/24"],
"state":{"ospf":False},"hints":["show ip ospf neighbor と show run。","R1のOSPFに10.0.12.0/30が参加しているか確認。","router ospf 1 → network 10.0.12.0 0.0.0.3 area 0。"]
},
{
"id":7,"ticket":"INC-307","title":"DNS OR NETWORK?","device":"PC-A","type":"dns",
"brief":"『wiki.corp.local が開かない』との申告。10.20.0.10へのpingは成功する。",
"spec":["PC-A: 192.168.10.20/24","GW: 192.168.10.1","社内DNS: 192.168.10.53","wiki.corp.local = 10.20.0.10","IP疎通は正常"],
"topology":["PC-A|192.168.10.20","DNS|192.168.10.53","R1|Gateway","WEB|10.20.0.10","NAME|wiki.corp.local"],
"state":{"dns":"192.168.10.99"},"hints":["IP疎通があるなら名前解決を切り分け。","ipconfig と nslookup を確認。","set dns 192.168.10.53。"]
},
{
"id":8,"ticket":"INC-308","title":"ACL LOCKOUT","device":"R1","type":"acl",
"brief":"管理PCからWebサーバーへpingは成功するがHTTPSだけ失敗。他の通信は正常。",
"spec":["管理PC: 192.168.50.10","WEB: 10.20.0.10","HTTPS TCP/443は許可する設計","ACL 101を使用","ルーティングは正常"],
"topology":["ADMIN|192.168.50.10","R1|ACL 101","CORE|Routed","WEB|10.20.0.10","HTTPS|TCP/443"],
"state":{"acl":False},"hints":["L3疎通済み。プロトコル単位の制御を確認。","show access-lists。","ACL 101で送信元host→WEB host eq 443をpermit。"]
},
{
"id":9,"ticket":"INC-309","title":"DHCP BLACKOUT","device":"R1","type":"dhcp",
"brief":"新規PCだけ169.254.x.xになる。固定IPの既存端末は正常。",
"spec":["LAN: 192.168.10.0/24","Default Gateway: 192.168.10.1","DHCP pool名: LAN","配布対象: 192.168.10.0/24","R1がDHCP Server"],
"topology":["NEW-PC|169.254.x.x","SW1|Access","R1|DHCP","LAN|192.168.10.0/24","GW|192.168.10.1"],
"state":{"dhcp":False,"dhcpnet":False,"dhcpgw":False},"hints":["show ip dhcp pool。","LAN poolが存在するか確認。","ip dhcp pool LAN → network → default-router。"]
},
{
"id":10,"ticket":"INC-310","title":"DOUBLE FAULT","device":"R1","type":"double",
"brief":"本社から支社サーバーへ完全に到達不能。保守作業後から発生。障害は1か所とは限らない。",
"spec":["R1 Gi0/1: 10.0.12.1/30","R2 Gi0/1: 10.0.12.2/30","Gi0/1は正常時UP","支社LAN: 10.30.0.0/24","R1は10.30.0.0/24を10.0.12.2へ送る"],
"topology":["HQ|192.168.10.0/24","R1|Gi0/1 .1","R2|Gi0/1 .2","BRANCH|10.30.0.0/24","SRV|10.30.0.10"],
"state":{"admin":False,"route":False},"hints":["OSI下位から順番に見ると楽。","Gi0/1を直した後も疎通確認を続ける。","Gi0/1 no shut ＋ static routeの両方が必要。"]
}
]

def new_state(level):
    m=copy.deepcopy(MISSIONS[level-1])
    return {"level":level,"device":m["device"],"type":m["type"],"data":m["state"],
            "mode":"user","iface":None,"commands":0,"hints":0}

def current_mission(s): return MISSIONS[s["level"]-1]

def prompt(s):
    d=s["device"]; m=s["mode"]
    suffix={"user":">","priv":"#","config":"(config)#","if":"(config-if)#",
            "router":"(config-router)#","dhcp":"(dhcp-config)#"}[m]
    return d+suffix

def is_pc(s): return s["type"] in ("gateway","dns")

def solved(s):
    d=s["data"]; k=s["type"]
    if k=="interface": return d.get("admin",False)
    if k=="gateway": return d.get("gateway")=="192.168.10.1"
    if k=="vlan": return d.get("vlan")==20
    if k=="trunk": return d.get("trunk",False)
    if k=="route": return d.get("route",False)
    if k=="ospf": return d.get("ospf",False)
    if k=="dns": return d.get("dns")=="192.168.10.53"
    if k=="acl": return d.get("acl",False)
    if k=="dhcp": return d.get("dhcpnet",False) and d.get("dhcpgw",False)
    if k=="double": return d.get("admin",False) and d.get("route",False)
    return False

def help_text(s):
    if is_pc(s):
        return "ipconfig\nping <address>\nnslookup <name>\nset gateway <address>\nset dns <address>"
    return "enable\nshow running-config\nshow ip interface brief\nshow ip route\nshow vlan brief\nshow interfaces trunk\nshow access-lists\nshow ip ospf neighbor\nshow ip dhcp pool\nping <address>\nconfigure terminal"

def execute(raw,s):
    c=" ".join(raw.strip().lower().split()); d=s["data"]; k=s["type"]; mode=s["mode"]
    if not c: return ""
    if c=="?" or c.endswith(" ?"): return help_text(s)

    # PC incidents
    if is_pc(s):
        if c=="ipconfig":
            gw=d.get("gateway","192.168.10.1"); dns=d.get("dns","192.168.10.53")
            return f"IPv4 Address . . . . . : 192.168.10.20\nSubnet Mask  . . . . . : 255.255.255.0\nDefault Gateway . . . .: {gw}\nDNS Servers . . . . . .: {dns}"
        if c.startswith("ping "):
            target=c.split()[-1]
            ok = (k=="gateway" and (target.startswith("192.168.10.") or solved(s))) or (k=="dns" and target=="10.20.0.10")
            return f"Pinging {target} with 32 bytes of data:\n"+("Reply from "+target+": bytes=32 time<1ms TTL=62" if ok else "Request timed out.")
        if c.startswith("nslookup "):
            return ("Server: 192.168.10.53\nName: wiki.corp.local\nAddress: 10.20.0.10" if solved(s)
                    else "DNS request timed out.\nServer: Unknown")
        if k=="gateway" and c=="set gateway 192.168.10.1":
            d["gateway"]="192.168.10.1"; return "Default gateway updated."
        if k=="dns" and c=="set dns 192.168.10.53":
            d["dns"]="192.168.10.53"; return "DNS server updated."
        return "'"+raw+"' is not recognized as a valid lab command."

    # IOS navigation
    if c in ("enable","en") and mode=="user": s["mode"]="priv"; return ""
    if c in ("disable",) and mode=="priv": s["mode"]="user"; return ""
    if c in ("configure terminal","conf t","conf ter") and mode=="priv":
        s["mode"]="config"; return "Enter configuration commands, one per line. End with CNTL/Z."
    if c=="end" and mode in ("config","if","router","dhcp"): s["mode"]="priv"; return ""
    if c=="exit" and mode in ("if","router","dhcp"): s["mode"]="config"; return ""
    if c=="exit" and mode=="config": s["mode"]="priv"; return ""
    if c.startswith("do ") and mode in ("config","if","router","dhcp"):
        old=s["mode"]; s["mode"]="priv"; out=execute(raw.strip()[3:],s); s["mode"]=old; return out

    # show
    if mode=="priv" and c in ("show ip interface brief","sh ip int br","sh ip int brief"):
        admin=d.get("admin",True)
        wan=("up                    up" if admin else "administratively down down")
        return "Interface              IP-Address      Status                Protocol\nGigabitEthernet0/0    192.168.10.1    up                    up\nGigabitEthernet0/1    10.0.12.1       "+wan
    if mode=="priv" and c in ("show vlan brief","sh vlan br"):
        v=d.get("vlan",20)
        return ("VLAN Name                             Status    Ports\n"
                "1    default                          active\n"
                "10   SALES                            active    Fa0/2"+(", Fa0/3" if v==10 else "")+"\n"
                "20   ACCOUNTING                       active"+("    Fa0/3" if v==20 else ""))
    if mode=="priv" and c in ("show interfaces trunk","sh int trunk"):
        return "Port      Mode   Encapsulation  Status        Native vlan\nGi0/24    on     802.1q         "+("trunking      1" if d.get("trunk",True) else "not-trunking  1")
    if mode=="priv" and c in ("show ip route","sh ip route"):
        lines=["C    192.168.10.0/24 is directly connected, GigabitEthernet0/0"]
        if d.get("admin",True): lines.append("C    10.0.12.0/30 is directly connected, GigabitEthernet0/1")
        if d.get("route", k not in ("route","double")): lines.append("S    10.30.0.0/24 [1/0] via 10.0.12.2")
        if k=="ospf" and d.get("ospf"): lines.append("O    10.40.0.0/24 [110/2] via 10.0.12.2")
        return "\n".join(lines)
    if mode=="priv" and c in ("show ip ospf neighbor","sh ip ospf nei"):
        return ("Neighbor ID Pri State    Dead Time Address   Interface\n2.2.2.2     1   FULL/DR  00:00:34  10.0.12.2 Gi0/1"
                if d.get("ospf",False) else "Neighbor ID Pri State Dead Time Address Interface")
    if mode=="priv" and c in ("show access-lists","sh access-lists"):
        return ("Extended IP access list 101\n 10 permit icmp any any\n 20 "+
                ("permit tcp host 192.168.50.10 host 10.20.0.10 eq 443" if d.get("acl",False)
                 else "deny tcp host 192.168.50.10 host 10.20.0.10 eq 443"))
    if mode=="priv" and c in ("show ip dhcp pool","sh ip dhcp pool"):
        if not d.get("dhcpnet",False): return "% No DHCP pools configured."
        return "Pool LAN :\n Utilization mark (high/low) : 100 / 0\n Subnet size : 254\n Network: 192.168.10.0 /24\n Default router: "+("192.168.10.1" if d.get("dhcpgw") else "not configured")
    if mode=="priv" and c in ("show running-config","show run","sh run"):
        lines=["hostname "+s["device"],"!"]
        if k in ("interface","double"):
            lines += ["interface GigabitEthernet0/1"," ip address 10.0.12.1 255.255.255.252"]
            if not d.get("admin"): lines.append(" shutdown")
        if k=="vlan": lines += ["interface FastEthernet0/3"," switchport mode access",f" switchport access vlan {d['vlan']}"]
        if k=="trunk": lines += ["interface GigabitEthernet0/24"," switchport mode "+("trunk" if d.get("trunk") else "access")]
        if k in ("route","double") and d.get("route"): lines += ["ip route 10.30.0.0 255.255.255.0 10.0.12.2"]
        if k=="ospf":
            lines += ["router ospf 1"]
            if d.get("ospf"): lines += [" network 10.0.12.0 0.0.0.3 area 0"]
        if k=="acl":
            lines += ["access-list 101 permit icmp any any",
                      "access-list 101 "+("permit" if d.get("acl") else "deny")+" tcp host 192.168.50.10 host 10.20.0.10 eq 443"]
        return "\n".join(lines+["!","end"])

    # config
    if mode=="config" and c.startswith("interface "):
        s["iface"]=c.split(None,1)[1]; s["mode"]="if"; return ""
    if mode=="if" and c in ("no shutdown","no shut"):
        d["admin"]=True; return "%LINK-3-UPDOWN: Interface changed state to up\n%LINEPROTO-5-UPDOWN: Line protocol changed state to up"
    if mode=="if" and c=="switchport access vlan 20": d["vlan"]=20; return ""
    if mode=="if" and c=="switchport mode trunk": d["trunk"]=True; return ""
    if mode=="config" and c=="ip route 10.30.0.0 255.255.255.0 10.0.12.2": d["route"]=True; return ""
    if mode=="config" and c=="router ospf 1": s["mode"]="router"; return ""
    if mode=="router" and c=="network 10.0.12.0 0.0.0.3 area 0": d["ospf"]=True; return ""
    if mode=="config" and c=="access-list 101 permit tcp host 192.168.50.10 host 10.20.0.10 eq 443":
        d["acl"]=True; return ""
    if mode=="config" and c=="ip dhcp pool lan": s["mode"]="dhcp"; return ""
    if mode=="dhcp" and c=="network 192.168.10.0 255.255.255.0": d["dhcpnet"]=True; return ""
    if mode=="dhcp" and c=="default-router 192.168.10.1": d["dhcpgw"]=True; return ""

    if mode in ("user","priv") and c.startswith("ping "):
        target=c.split()[-1]; ok=solved(s)
        return f"Sending 5, 100-byte ICMP Echos to {target}:\n"+("!!!!!\nSuccess rate is 100 percent (5/5)" if ok else ".....\nSuccess rate is 0 percent (0/5)")
    return "% Invalid input detected at '^' marker."

@app.route("/")
def index(): return render_template("index.html")

@app.get("/api/missions")
def missions():
    return jsonify([{"id":m["id"],"ticket":m["ticket"],"title":m["title"],"device":m["device"]} for m in MISSIONS])

@app.post("/api/start")
def start():
    level=int((request.json or {}).get("level",1)); level=max(1,min(10,level))
    s=new_state(level); session["state"]=copy.deepcopy(s); session.modified=True
    m=current_mission(s)
    return jsonify(mission={"id":m["id"],"ticket":m["ticket"],"title":m["title"],"device":m["device"],
                            "brief":m["brief"],"spec":m["spec"],"topology":m["topology"]},
                   prompt=prompt(s))

@app.post("/api/cmd")
def cmd():
    s=copy.deepcopy(session.get("state") or new_state(1))
    s["commands"]+=1
    out=execute((request.json or {}).get("command",""),s)
    session["state"]=copy.deepcopy(s); session.modified=True
    score=max(100,1000-s["commands"]*10-s["hints"]*125)
    return jsonify(output=out,prompt=prompt(s),solved=solved(s),score=score)

@app.post("/api/hint")
def hint():
    s=copy.deepcopy(session.get("state") or new_state(1)); m=current_mission(s)
    s["hints"]+=1; session["state"]=copy.deepcopy(s); session.modified=True
    return jsonify(hint=m["hints"][min(s["hints"]-1,len(m["hints"])-1)])

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
