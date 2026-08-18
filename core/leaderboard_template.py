"""
NTE 刮刮乐 - 排行榜 HTML 模板

独立存放排行榜图片渲染的 HTML 模板，便于维护，不随插件主逻辑混在一起。
"""

# 排行榜 HTML 模板
LEADERBOARD_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link rel="stylesheet" crossorigin="anonymous" href="https://cdn.jsdelivr.net/npm/misans@4.1.0/lib/Normal/MiSans-Medium.min.css" /> 
<link rel="stylesheet" crossorigin="anonymous" href="https://cdn.jsdelivr.net/npm/misans@4.1.0/lib/Normal/MiSans-Bold.min.css" />
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:fit-content}
body{font-family:"MiSans",sans-serif;width:840px;}
.outer-frame{background: linear-gradient(180deg, #232225, #FFF584);width: 840px;padding: 16px;min-height:100vh;}
.title{text-align:right;font-size:42px;font-weight:1000;transform:skewX(-7deg);color:#F0C954;padding:8px 16px 12px 0}
.header{display:flex;align-items:center;background:linear-gradient(180deg,#3a3020,#2a2218);border:1px solid rgba(0,0,0,.1);border-radius:12px;margin-bottom:12px}
.header div{font-size:20px;font-weight:700;color:#D2D2D2;-webkit-text-stroke:#000000 1px}
.h-rank{flex:260 0 0;text-align:center;background:#9F7D42;border-radius:12px 0 0 12px}
.h-name{flex:790 0 0;padding:0 16px;background:#7D46A2}
.h-name span{padding-left:100px}
.h-money{flex:510 0 0;text-align:center;background:#464544;padding:0 15px 0 0;border-radius:0 12px 12px 0}
.h-rank span,.h-name span,.h-money span{display:inline-block;transform:skewX(-7deg)}
.card{margin-bottom:8px;overflow:hidden}
.row{display:flex;align-items:stretch;min-height:78px;overflow:hidden;position:relative}
.badge{flex:260 0 0;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;--r:6px;-webkit-mask:radial-gradient(circle at 8px 8px,transparent var(--r),#fff var(--r)) -8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) 8px,transparent var(--r),#fff var(--r)) 8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) calc(100% - 8px),transparent var(--r),#fff var(--r)) 8px 8px/100% 100% no-repeat,radial-gradient(circle at 8px calc(100% - 8px),transparent var(--r),#fff var(--r)) -8px 8px/100% 100% no-repeat;mask:radial-gradient(circle at 8px 8px,transparent var(--r),#fff var(--r)) -8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) 8px,transparent var(--r),#fff var(--r)) 8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) calc(100% - 8px),transparent var(--r),#fff var(--r)) 8px 8px/100% 100% no-repeat,radial-gradient(circle at 8px calc(100% - 8px),transparent var(--r),#fff var(--r)) -8px 8px/100% 100% no-repeat}
.badge::before{content:'';position:absolute;inset:0;pointer-events:none;--r:8px;--w:2px;--c:#3C3833;--xc:#838383;background:radial-gradient(var(--r) at var(--r) var(--r),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) calc(-1*var(--r)) calc(-1*var(--r))/100% 100% no-repeat,radial-gradient(var(--r) at calc(100% - var(--r)) var(--r),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) var(--r) calc(-1*var(--r))/100% 100% no-repeat,radial-gradient(var(--r) at calc(100% - var(--r)) calc(100% - var(--r)),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) var(--r) var(--r)/100% 100% no-repeat,radial-gradient(var(--r) at var(--r) calc(100% - var(--r)),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) calc(-1*var(--r)) var(--r)/100% 100% no-repeat,linear-gradient(var(--c),var(--c)) var(--r) 0/calc(100% - 2*var(--r)) var(--w) no-repeat,linear-gradient(var(--c),var(--c)) var(--r) 100%/calc(100% - 2*var(--r)) var(--w) no-repeat,linear-gradient(var(--c),var(--c)) 0 var(--r)/var(--w) calc(100% - 2*var(--r)) no-repeat,repeating-linear-gradient(to bottom,var(--xc) 0,var(--xc) 3px,transparent 3px,transparent 6px) 100% var(--r)/var(--w) calc(100% - 2*var(--r)) no-repeat}
.badge .num{font-size:32px;font-weight:900;line-height:1;color:#FFF;transform:skewX(-7deg);-webkit-text-stroke:2px #090909;z-index:1}
.badge .line{position:absolute;right:0;top:10%;height:80%;width:1px}
.name-section{flex:790 0 0;display:flex;flex-direction:column;justify-content:space-between;padding:5px 16px;position:relative;min-width:0;background:linear-gradient(180deg,#DDD,#FFF);--r:6px;-webkit-mask:radial-gradient(circle at 8px 8px,transparent var(--r),#fff var(--r)) -8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) 8px,transparent var(--r),#fff var(--r)) 8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) calc(100% - 8px),transparent var(--r),#fff var(--r)) 8px 8px/100% 100% no-repeat,radial-gradient(circle at 8px calc(100% - 8px),transparent var(--r),#fff var(--r)) -8px 8px/100% 100% no-repeat;mask:radial-gradient(circle at 8px 8px,transparent var(--r),#fff var(--r)) -8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) 8px,transparent var(--r),#fff var(--r)) 8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) calc(100% - 8px),transparent var(--r),#fff var(--r)) 8px 8px/100% 100% no-repeat,radial-gradient(circle at 8px calc(100% - 8px),transparent var(--r),#fff var(--r)) -8px 8px/100% 100% no-repeat}
.name-section::before{content:'';position:absolute;inset:0;pointer-events:none;--r:8px;--w:2px;--c:#3C3833;--xc:#838383;background:radial-gradient(var(--r) at var(--r) var(--r),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) calc(-1*var(--r)) calc(-1*var(--r))/100% 100% no-repeat,radial-gradient(var(--r) at calc(100% - var(--r)) var(--r),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) var(--r) calc(-1*var(--r))/100% 100% no-repeat,radial-gradient(var(--r) at calc(100% - var(--r)) calc(100% - var(--r)),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) var(--r) var(--r)/100% 100% no-repeat,radial-gradient(var(--r) at var(--r) calc(100% - var(--r)),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) calc(-1*var(--r)) var(--r)/100% 100% no-repeat,linear-gradient(var(--c),var(--c)) var(--r) 0/calc(100% - 2*var(--r)) var(--w) no-repeat,linear-gradient(var(--c),var(--c)) var(--r) 100%/calc(100% - 2*var(--r)) var(--w) no-repeat,repeating-linear-gradient(to bottom,var(--xc) 0,var(--xc) 3px,transparent 3px,transparent 6px) 0 var(--r)/var(--w) calc(100% - 2*var(--r)) no-repeat,repeating-linear-gradient(to bottom,var(--xc) 0,var(--xc) 3px,transparent 3px,transparent 6px) 100% var(--r)/var(--w) calc(100% - 2*var(--r)) no-repeat}
.id-prefix{font-size:8px;padding:0 8px;color:#000;background:#A2A2A2;border-radius:8px}
.id-text{font-size:8px;opacity:.5;margin-bottom:3px;font-weight:700}
.name-text{font-size:18px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-left:100px}
.barcode{margin-top:6px;height:10px;width:80px}
.money-section{flex:510 0 0;display:flex;align-items:center;justify-content:flex-end;padding:12px 15px 12px 0;gap:10px;background:linear-gradient(180deg,#DDD,#FFF);position:relative;--r:6px;-webkit-mask:radial-gradient(circle at 8px 8px,transparent var(--r),#fff var(--r)) -8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) 8px,transparent var(--r),#fff var(--r)) 8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) calc(100% - 8px),transparent var(--r),#fff var(--r)) 8px 8px/100% 100% no-repeat,radial-gradient(circle at 8px calc(100% - 8px),transparent var(--r),#fff var(--r)) -8px 8px/100% 100% no-repeat;mask:radial-gradient(circle at 8px 8px,transparent var(--r),#fff var(--r)) -8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) 8px,transparent var(--r),#fff var(--r)) 8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) calc(100% - 8px),transparent var(--r),#fff var(--r)) 8px 8px/100% 100% no-repeat,radial-gradient(circle at 8px calc(100% - 8px),transparent var(--r),#fff var(--r)) -8px 8px/100% 100% no-repeat}
.money-section::before{content:'';position:absolute;inset:0;pointer-events:none;--r:8px;--w:2px;--c:#3C3833;--xc:#838383;background:radial-gradient(var(--r) at var(--r) var(--r),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) calc(-1*var(--r)) calc(-1*var(--r))/100% 100% no-repeat,radial-gradient(var(--r) at calc(100% - var(--r)) var(--r),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) var(--r) calc(-1*var(--r))/100% 100% no-repeat,radial-gradient(var(--r) at calc(100% - var(--r)) calc(100% - var(--r)),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) var(--r) var(--r)/100% 100% no-repeat,radial-gradient(var(--r) at var(--r) calc(100% - var(--r)),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) calc(-1*var(--r)) var(--r)/100% 100% no-repeat,linear-gradient(var(--c),var(--c)) var(--r) 0/calc(100% - 2*var(--r)) var(--w) no-repeat,linear-gradient(var(--c),var(--c)) var(--r) 100%/calc(100% - 2*var(--r)) var(--w) no-repeat,linear-gradient(var(--c),var(--c)) 100% var(--r)/var(--w) calc(100% - 2*var(--r)) no-repeat,repeating-linear-gradient(to bottom,var(--xc) 0,var(--xc) 3px,transparent 3px,transparent 6px) 0 var(--r)/var(--w) calc(100% - 2*var(--r)) no-repeat}
.coin-icon{height:24px;width:auto;flex-shrink:0;margin-right:0}
.money-text{font-size:25px;font-weight:900;color:#FFC431;-webkit-text-stroke:1.5px #090909;text-stroke:1px #090909}
.hot-tag{position:absolute;right:16px;bottom:4px;font-size:8px;letter-spacing:1px;opacity:.25;font-weight:700}
.dash{width:1px;align-self:stretch;margin:12px 0;border-left:1px dashed rgba(150,130,80,.4);flex-shrink:0}
.card-normal .badge{background:#5D7893}
.card-normal .badge .line{background:#c0b090}
.card-normal .name-text{color:#2a2218}
.card-normal .id-text{color:#a09070}
.card-normal .barcode{background:repeating-linear-gradient(90deg,transparent 0,transparent 2px,rgba(100,80,40,.12) 2px,rgba(100,80,40,.12) 3px,transparent 3px,transparent 5px)}
.card-normal .dash{border-left-color:#c0b090}
.card-normal .hot-tag{color:#a09070}
.card-r1 .badge{background:linear-gradient(180deg,#c8a030,#8a6a18)}
.card-r2 .badge{background:linear-gradient(180deg,#b0b0b0,#707070)}
.card-r3 .badge{background:linear-gradient(180deg,#c08040,#7a4a20)}
</style></head><body>
<div class="outer-frame">
<div class="title">{{ title }}</div>
<div class="header">
    <div class="h-rank"><span>排名</span></div>
    <div class="h-name"><span>名称</span></div>
    <div class="h-money"><span>财富值</span></div>
</div>
{% for item in items %}
<div class="card card-normal {% if item.rank <= 3 %}card-r{{ item.rank }}{% endif %}">
    <div class="row">
        <div class="badge"><div class="num">{{ item.rank }}</div></div>
        <div class="name-section">
            <div class="id-text"><span class="id-prefix">NTE</span> NO.{{ '%06d' % item.uid_int if item.uid_int else '000000' }}</div>
            <div class="name-text">{{ item.name }}</div>
            <div class="barcode"></div>
        </div>
        <div class="money-section"><img src="{{ coin_icon }}" alt="Coin" class="coin-icon"><div class="money-text">{{ item.amount }}</div></div>
    </div>
</div>
{% endfor %}
</div>
</body></html>"""
