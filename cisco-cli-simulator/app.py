from flask import Flask,render_template,request,jsonify,session
import os,copy
app=Flask(__name__);app.secret_key=os.environ.get("SECRET_KEY","dev-key")

MISSIONS=[
{"id":1,"host":"R1","title":"THE SILENT UPLINK","ticket":"INC-2048","brief":"PC-Aから社内Webサーバーへ到達できない。朝から突然つながらない。R1を調査して復旧せよ。","kind":"if","data":{"admin":False}},
{"id":2,"host":"PC-A","title":"WRONG GATEWAY","ticket":"INC-2051","brief":"開発PCから別セグメントへ通信できない。同一LAN内の通信は正常。端末設定を調査して復旧せよ。","kind":"gw","data":{"gateway":"192.168.10.254"}},
{"id":3,"host":"SW1","title":"VLAN DRIFT","ticket":"INC-2057","brief":"経理PCだけ社内ネットワークへ接続できない。同じスイッチの他部署PCは正常。SW1を調査せよ。","kind":"vlan","data":{"vlan":10,"mode":"access"}},
{"id":4,"host":"SW1","title":"TRUNK LOST","ticket":"INC-2062","brief":"VLAN 10の端末から別スイッチ側の同一VLAN端末へ通信できない。SW1-SW2間を調査せよ。","kind":"trunk","data":{"trunk":False}},
{"id":5,"host":"R1","title":"MISSING ROUTE","ticket":"INC-2070","brief":"R1から支社LAN 10.30.0.0/24へ到達できない。WANリンク自体は正常。ルーティングを調査せよ。","kind":"route","data":{"route":False}},
{"id":6,"host":"R1","title":"OSPF SILENCE","ticket":"INC-2078","brief":"R1とR2のリンクはUPだが、OSPFで経路交換されない。R1の設定を調査せよ。","kind":"ospf","data":{"ospf":False}},
{"id":7,"host":"PC-A","title":"DNS OR NETWORK?","ticket":"INC-2084","brief":"ユーザーから『社内Wikiが開けない』と連絡。IP直打ちでは挙動が違うらしい。原因を切り分けよ。","kind":"dns","data":{"dns":"192.168.10.99"}},
{"id":8,"host":"R1","title":"ACL LOCKOUT","ticket":"INC-2091","brief":"管理PCからWebサーバーへのHTTPSだけ失敗する。ICMPは通る。R1のフィルタ設定を調査せよ。","kind":"acl","data":{"acl":False}},
{"id":9,"host":"R1","title":"DHCP BLACKOUT","ticket":"INC-2099","brief":"新しく接続したPCが169.254.x.xになり通信できない。既存端末は正常。DHCP設定を調査せよ。","kind":"dhcp","data":{"dhcp":False}},
{"id":10,"host":"R1","title":"DOUBLE FAULT","ticket":"INC-2105","brief":"支社サーバーへの通信が完全に停止。今回は障害が1か所とは限らない。調査・復旧・疎通確認まで行え。","kind":"double","data":{"admin":False,"route":False}},
]
def mission(n): return copy.deepcopy(MISSIONS[max(0,min(9,n-1))])
def prompt(s):
 h=s["host"];m=s["mode"]
 return h+({"user":">","priv":"#","config":"(config)#","if":"(config-if)#","router":"(config-router)#","dhcp":"(dhcp-config)#"}[m])
def solved(s):
 d=s["data"];k=s["kind"]
 return {"if":d["admin"],"gw":d["gateway"]=="192.168.10.1","vlan":d["vlan"]==20,"trunk":d["trunk"],"route":d["route"],"ospf":d["ospf"],"dns":d["dns"]=="192.168.10.53","acl":d["acl"],"dhcp":d["dhcp"],"double":d["admin"] and d["route"]}[k]
def exec_cmd(raw,s):
 c=" ".join(raw.lower().strip().split());d=s["data"];k=s["kind"];m=s["mode"]
 if not c:return ""
 if c.endswith("?"):return "enable\nshow running-config\nshow ip interface brief\nshow ip route\nshow vlan brief\nshow interfaces trunk\nshow access-lists\nshow ip ospf neighbor\nshow ip dhcp pool\nping <address>\nconfigure terminal"
 if c in ("enable","en") and m=="user":s["mode"]="priv";return ""
 if c in ("conf t","configure terminal") and m=="priv":s["mode"]="config";return "Enter configuration commands, one per line. End with CNTL/Z."
 if c=="end" and m not in ("user","priv"):s["mode"]="priv";return ""
 if c=="exit" and m in ("if","router","dhcp"):s["mode"]="config";return ""
 if c=="exit" and m=="config":s["mode"]="priv";return ""
 if c.startswith("do ") and m not in ("user","priv"):
  old=s["mode"];s["mode"]="priv";o=exec_cmd(raw.strip()[3:],s);s["mode"]=old;return o
 if k in ("gw","dns") and c in ("ipconfig","show ip","show ip config"):
  return f"IPv4 Address . . . : 192.168.10.20\nSubnet Mask  . . . : 255.255.255.0\nDefault Gateway . .: {d.get('gateway','192.168.10.1')}\nDNS Servers . . . . : {d.get('dns','192.168.10.53')}"
 if k=="gw" and c.startswith("set gateway "):d["gateway"]=c.split()[-1];return "Default gateway updated."
 if k=="dns" and c.startswith("set dns "):d["dns"]=c.split()[-1];return "DNS server updated."
 if m=="priv" and c in ("show ip interface brief","sh ip int br"):
  admin=d.get("admin",True)
  return "Interface              IP-Address      Status                Protocol\nGigabitEthernet0/0    192.168.10.1    up                    up\nGigabitEthernet0/1    10.0.12.1       "+("up                    up" if admin else "administratively down down")
 if m=="priv" and c in ("show vlan brief","sh vlan br"):
  v=d.get("vlan",20);return f"VLAN Name                             Status    Ports\n1    default                          active\n10   SALES                            active\n20   ACCOUNTING                       active    Fa0/3" if v==20 else f"VLAN Name                             Status    Ports\n1    default                          active\n10   SALES                            active    Fa0/3\n20   ACCOUNTING                       active"
 if m=="priv" and c in ("show interfaces trunk","sh int trunk"):
  return "Port        Mode   Encapsulation Status    Native vlan\nGi0/24      on     802.1q        "+("trunking  1" if d.get("trunk",True) else "not-trunking 1")
 if m=="priv" and c in ("show ip route","sh ip route"):
  base="C 192.168.10.0/24 is directly connected, Gi0/0\nC 10.0.12.0/30 is directly connected, Gi0/1"
  return base+("\nS 10.30.0.0/24 [1/0] via 10.0.12.2" if d.get("route",True) else "")
 if m=="priv" and c in ("show ip ospf neighbor","sh ip ospf nei"):
  return "Neighbor ID Pri State Dead Time Address Interface\n2.2.2.2 1 FULL/DR 00:00:34 10.0.12.2 Gi0/1" if d.get("ospf",True) else ""
 if m=="priv" and c in ("show access-lists","sh access-lists"):
  return "Extended IP access list 101\n 10 permit icmp any any\n 20 "+("permit tcp host 192.168.50.10 host 10.20.0.10 eq 443" if d.get("acl",True) else "deny tcp any host 10.20.0.10 eq 443")
 if m=="priv" and c in ("show ip dhcp pool","sh ip dhcp pool"):
  return "Pool LAN : 192.168.10.0/24, default-router 192.168.10.1" if d.get("dhcp",True) else "% No DHCP pools configured."
 if m=="priv" and c in ("show running-config","show run","sh run"):
  lines=["hostname "+s["host"]]
  if k in ("if","double"):lines+=["interface GigabitEthernet0/1"," ip address 10.0.12.1 255.255.255.252"]+([" shutdown"] if not d["admin"] else [])
  if k=="vlan":lines+=["interface FastEthernet0/3"," switchport mode access",f" switchport access vlan {d['vlan']}"]
  if k=="trunk":lines+=["interface GigabitEthernet0/24"]+([" switchport mode trunk"] if d["trunk"] else [" switchport mode access"])
  if k in ("route","double") and d["route"]:lines+=["ip route 10.30.0.0 255.255.255.0 10.0.12.2"]
  if k=="ospf":lines+=["router ospf 1"]+([" network 10.0.12.0 0.0.0.3 area 0"] if d["ospf"] else [])
  return "\n".join(lines)
 if m=="config" and c.startswith("interface "):s["mode"]="if";s["iface"]=c.split(None,1)[1];return ""
 if m=="if" and c in ("no shutdown","no shut"):d["admin"]=True;return "%LINK-3-UPDOWN: Interface changed state to up"
 if m=="if" and c=="switchport access vlan 20":d["vlan"]=20;return ""
 if m=="if" and c=="switchport mode trunk":d["trunk"]=True;return ""
 if m=="config" and c=="ip route 10.30.0.0 255.255.255.0 10.0.12.2":d["route"]=True;return ""
 if m=="config" and c=="router ospf 1":s["mode"]="router";return ""
 if m=="router" and c=="network 10.0.12.0 0.0.0.3 area 0":d["ospf"]=True;return ""
 if m=="config" and c=="access-list 101 permit tcp host 192.168.50.10 host 10.20.0.10 eq 443":d["acl"]=True;return ""
 if m=="config" and c=="ip dhcp pool lan":s["mode"]="dhcp";return ""
 if m=="dhcp" and c=="network 192.168.10.0 255.255.255.0":d["dhcpnet"]=True;return ""
 if m=="dhcp" and c=="default-router 192.168.10.1":d["dhcpgw"]=True;d["dhcp"]=bool(d.get("dhcpnet"));return ""
 if c.startswith("ping "):
  good=solved(s)
  return f"Sending 5, 100-byte ICMP Echos...\n{'!!!!!' if good else '.....'}\nSuccess rate is {'100 percent (5/5)' if good else '0 percent (0/5)'}"
 return "% Invalid input detected at '^' marker."
@app.route("/")
def index():return render_template("index.html")
@app.post("/api/start")
def start():
 n=int((request.json or {}).get("level",1));x=mission(n);s={"level":n,"host":x["host"],"title":x["title"],"ticket":x["ticket"],"brief":x["brief"],"kind":x["kind"],"data":x["data"],"mode":"user","commands":0,"hints":0};session["s"]=s
 return jsonify(state=s,prompt=prompt(s))
@app.post("/api/cmd")
def cmd():
 s=session["s"];s["commands"]+=1;o=exec_cmd(request.json.get("command",""),s);session["s"]=s;score=max(100,1000-s["commands"]*10-s["hints"]*150)
 return jsonify(output=o,prompt=prompt(s),solved=solved(s),score=score)
@app.post("/api/hint")
def hint():
 s=session["s"];s["hints"]+=1;k=s["kind"];hs={"if":["インターフェース状態を見てみよ。","administratively down に注目。","Gi0/1 の shutdown を解除。"],"gw":["端末自身のIP設定を確認。","Default Gatewayがおかしくない？","正しいGWは192.168.10.1。"],"vlan":["VLAN membershipを確認。","Fa0/3の所属VLANに注目。","経理はVLAN 20。"],"trunk":["スイッチ間リンクを確認。","Gi0/24がtrunkingしてへん。","switchport mode trunk。"],"route":["ルーティングテーブルを確認。","10.30.0.0/24が無い。","next-hopは10.0.12.2。"],"ospf":["OSPF neighborを確認。","R1のOSPF network文を確認。","10.0.12.0/30をarea 0へ。"],"dns":["IP設定と名前解決を分けて考えよ。","DNSサーバー設定を確認。","正しいDNSは192.168.10.53。"],"acl":["ICMPは通る＝経路自体はありそう。","ACLを確認。","192.168.50.10→10.20.0.10 TCP/443をpermit。"],"dhcp":["DHCP poolを確認。","pool自体が無い。","LAN poolを作りnetworkとdefault-routerを設定。"],"double":["1個直して終わりとは限らんで。","Gi0/1とrouting両方を見る。","no shut後、10.30.0.0/24のstatic routeも必要。"]}[k]
 return jsonify(hint=hs[min(s["hints"]-1,len(hs)-1)])
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
