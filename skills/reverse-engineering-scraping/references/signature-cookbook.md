# 签名算法 cookbook

> 目标：把"我抓到的请求"翻译成"我能在 Python 里重算的签名函数"。
> 顺序建议：先用 `revkit breakread` 拿明文 → 再对照本文判定算法 → 最后用 `revkit solve` 复核。

## 0. 先判断签名"喂"的是什么
命中签名函数后，看**入参字符串**。它几乎总是下列之一：

| 明文形态 | 含义 |
|---|---|
| `a=1&b=2&key=XXXX` | 参数按 **key 排序** 拼接 + 盐（最常见） |
| `a=1&b=2` | 纯参数拼接，盐在函数内部另加 |
| `{"a":1,"b":2}` | JSON 体签名 |
| 一串密文/base64 | 多层嵌套：先加密再签名，或签名后再加密 |
| 含 `1791490344573` | 时间戳参与（复现时必须现取） |

## 1. 哈希类（占国内电商 80%）

```python
import hashlib, hmac, time, base64

# MD5(sorted + salt)，输出常为大写
def sign_md5(params: dict, salt: str) -> str:
    raw = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "sign") + f"&key={salt}"
    return hashlib.md5(raw.encode()).hexdigest()          # 大写: .upper()

# HMAC-SHA256
def sign_hmac(params: dict, secret: str) -> str:
    raw = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "sign")
    return hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()

# 变体：Base64(原始摘要字节)
base64.b64encode(bytes.fromhex(sign_md5(p, s))).decode()
```

**输出变体**（同一算法不同站）：
- 大写 / 小写
- 取前 16 位 / 后 16 位 / 前 32 位
- hex → 再 base64
- 拼时间戳后缀

## 2. 对称加密（key 常硬编码在 JS 里）

```python
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

def aes_ecb_b64(key: bytes, plaintext: bytes) -> str:
    pad = padding.PKCS7(128).padder()
    data = pad.update(plaintext) + pad.finalize()
    enc = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return base64.b64encode(enc.update(data) + enc.finalize()).decode()
```
- 常见：`AES/ECB/PKCS7`、`AES/CBC`（iv 常是 key 或全 0）
- key 常见来源：**JS 里一个固定字符串**、或 `md5(固定串)[:16]`
- CryptoJS 的 `CryptoJS.AES.encrypt(text, key)` 默认就是 **CBC + Pkcs7 + 随机 salt**（OpenSSL 格式），拿密文能解但需带 `U2FsdGVkX1` 头判断

## 3. 时间戳 / nonce
- `ts`/`_t`/`wts` 参与签名 → **必须现算**，抓包时的旧值不能用
- 部分站点校验窗口（±60s / ±5min）→ 复现必须快
- `revkit replay --refresh-ts` 会自动刷 `ts|_t|timestamp|time` 参数，但**签名要你自己重算**（刷了 ts 旧 sign 就失效）

## 4. 混淆的识别与对付
| 特征 | 说明 | 对策 |
|---|---|---|
| 长数组 + 下标取值 | webpack 打包的字符串数组 | 浏览器里执行后读值，别静态还原 |
| 大量 `_0x` 变量名 | obfuscator.io 类 | `breakread` 断点读明文 |
| `switch` 大循环 | 控制流平坦化 | 同上，别反平坦化 |
| `eval` / `Function(...)` | 动态执行 | hook `eval`/`Function` 看真实代码 |
| 自研 MD5/SHA | 直接内联实现 | 断点读入参最稳（本技能靶场即此类） |

## 5. 用 `revkit solve` 自动试
给参数与签名值，工具会穷举 `md5/sha1/sha256/hmac-*` × 8 种拼接顺序 × 盐候选 × 3 种输出：
```bash
$PY $RK solve --params "sku=A1&page=1&ts=1791490344573" --sign "8e2bd78c..." --salts "6a4c3f2a9b1c,candidate2"
```
**盐候选从哪来**：`breakread` 读出的明文里直接就有；或静态看 JS 里形如 `["...","...","..."]` 的数组。

## 6. 真实世界对照
- **bilibili WBI**：接口带 `w_rid`（签名）+ `wts`（时间戳）。算法 = 对参数按 key 排序 → 用从 `img_key/sub_key` 换来的 `mixin_key` 混入 → `md5` → `w_rid`。**img_key/sub_key 会变**，要定期从 `/x/web-interface/nav` 重新取。
- **抖音 a_bogus / X-Bogus**：强混淆 + 环境检测，属高难度，优先考虑官方开放平台或第三方合规数据源。
- **淘宝/京东 H5 api**：多为 `sign = md5(sorted + token + appKey + ts)`，token 来自登录态。

## 7. 判定不清时的下一步
1. 加 `breakread --depth 8` 往调用栈更深看
2. 在**更靠上**的层设断点（比如 `JSON.stringify`、`btoa`、`encodeURIComponent` 的调用点）
3. 用 `hooks` 挂 CryptoJS/js-md5，若站点用了这些库会直接吐明文
4. 若入参已是密文 → 你在加密**之后**才断到，往上层挪
