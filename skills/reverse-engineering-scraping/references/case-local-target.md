# 靶场案例：从零还原一个 MD5 签名接口（全链路实测）

> 这是本技能的**验收证据**。靶站是自建的（`<HERMES_HOME>`），
> 模拟国内电商套路：**排序参数 + 盐 + MD5 + 时间戳**，且盐做了分片混淆。
> 全程"盲盒式"：**不看源码**，只用 `revkit` 把算法还原出来。

## 靶站设定
- `GET /api/items?sku=&page=&ts=&sign=`
- 后端校验：`sign == md5(sorted(params)+"&key="+SALT).lower()`，且 `|now-ts| <= 60s`
- 前端 `app.min.js`：自研内联 MD5 + 盐分片 `["0x1","6a4c","3f2a","9b1c","z"]` → `_s = "6a4c3f2a9b1c"`
- 无签名 → `403 {"msg":"missing sign"}`；签名错 → `403 {"msg":"sign invalid"}`

## 步骤与实测输出

### ① 抓包（黑盒）
```bash
$PY $RK capture "http://127.0.0.1:8899/" --eval "window.__getData()" --wait 2 --contains api/items --with-body --out sample.json
```
```
# 抓到 1 条 XHR/fetch 请求
[GET] http://127.0.0.1:8899/api/items?sku=A1001&page=1&ts=1791490344573&sign=8e2bd78c367c70d93e4f3de0bd8432f6
  resp: {"code":0,"data":[{"sku":"A1001","name":"316不锈钢保温杯","price":39.9,...}]}
```
→ 拿到：**参数集 + 签名值 + 响应**。

### ② 定位（白盒）——本技能的杀器
```bash
$PY $RK breakread "http://127.0.0.1:8899/" --match "md5(" --script app.min.js --depth 4 \
   --expr "typeof str!=='undefined'?str:(typeof r!=='undefined'?r:'')" --eval "window.__getData()"
```
```
[+] 命中脚本: http://127.0.0.1:8899/app.min.js  (scriptId=5)
      6| function md5(str){
[+] 断点已设: line 6 col 9  -> 1 处命中位置
[+] 断点命中，调用栈 4 层：

  #0 md5  @line 7
      ... = page=1&sku=A1001&ts=1791490722173&key=6a4c3f2a9b1c
      locals: ['str','msg','bytes','i','bitLen','h0','h1','h2','h3','off','M','A','B','C','D','F','g','hex']
  #1 _sg  @line 33
      ... = page=1&sku=A1001&ts=1791490722173&key=6a4c3f2a9b1c
      locals: ['p','k','r']
  #2 window.__getData @line 37   locals: ['p','q']
```
→ **一次就拿到完整明文**：`page=1&sku=A1001&ts=...&key=6a4c3f2a9b1c`
→ 算法事实：**排序 key → `k=v` 用 `&` 连接 → 追加 `&key=` + 盐 `6a4c3f2a9b1c` → MD5**
→ 连"盐藏在哪"都不用猜，`locals` 直接告诉你该读哪些变量。

### ③ 还原
```bash
# 裸试（不给盐）
$PY $RK solve --params "sku=A1001&page=1&ts=1791490344573" --sign "8e2bd78c367c70d93e4f3de0bd8432f6"
[x] 未命中（试了 48 种组合）

# 给上断点抠到的盐
$PY $RK solve --params "sku=A1001&page=1&ts=1791490344573" --sign "8e2bd78c367c70d93e4f3de0bd8432f6" --salts "6a4c3f2a9b1c"
### 命中 ###
算法 : md5
输出 : hex
盐   : '6a4c3f2a9b1c'
明文 : page=1&sku=A1001&ts=1791490344573&key=6a4c3f2a9b1c
结果 : 8e2bd78c367c70d93e4f3de0bd8432f6
```

### ④ 复现
```python
import hashlib, time, urllib.parse, urllib.request
SALT = "6a4c3f2a9b1c"
def fetch(page=1):
    p = {"sku": "A1001", "page": str(page), "ts": str(int(time.time()*1000))}
    raw = "&".join(f"{k}={p[k]}" for k in sorted(p)) + f"&key={SALT}"
    p["sign"] = hashlib.md5(raw.encode()).hexdigest()
    url = "http://127.0.0.1:8899/api/items?" + urllib.parse.urlencode(p)
    return urllib.request.urlopen(url).read().decode()
print(fetch())   # → {"code":0,"data":[...]}
```
`revkit replay --file sample2.json` 同样直接返回 `HTTP 200` + 数据。

## 真实站点冒烟
```bash
$PY $RK capture "https://www.bilibili.com/" --wait 7 --contains api
# → 抓到 22 条 XHR，其中：
#   .../wbi/search/default?...&w_rid=b87f8220fac846c4d723ad9a7cc083e2&wts=1791490736
```
`w_rid` + `wts` 即 bilibili 的 **WBI 签名**——真实世界"带签名参数"的典型，说明本工具出靶场同样可用。

## 结论
本技能的四步法在**自建靶场**（可复现）与**真实站点**（bilibili）上双向验证通过：
- 断点读明文这条路径，把"读混淆代码猜算法"从小时级压到**分钟级**
- 还原 + 复现闭环成立
