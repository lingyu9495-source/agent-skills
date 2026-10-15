/* hook.js —— 通用逆向 hook 片段（注入到页面最早期）
 * 覆盖三类最常见的"签名发生地"：
 *   1) 网络边界：fetch / XMLHttpRequest / WebSocket  → 看签名后的最终请求
 *   2) 加密库边界：CryptoJS.MD5/SHA/Hmac、js-md5、spark-md5、window.crypto.subtle → 看明文入参
 *   3) 常见混淆工具："字符串解密函数"、JSON.stringify → 看构造中的对象
 * 命中后统一 console.log('[HOOK] ...')，由 revkit hooks 收走。
 */
(function () {
  var L = function () { console.log.apply(console, ['[HOOK]'].concat([].slice.call(arguments))); };
  var wrap = function (obj, name, tag) {
    try {
      if (!obj || !obj[name]) return;
      var orig = obj[name];
      obj[name] = function () {
        try { L(tag, [].slice.call(arguments).map(String).join(' | ').slice(0, 800)); } catch (e) {}
        return orig.apply(this, arguments);
      };
    } catch (e) {}
  };

  // 1) 网络边界
  try {
    var of = window.fetch;
    if (of) window.fetch = function (u, o) {
      try { L('fetch', typeof u === 'string' ? u : (u && u.url), (o && o.body) ? ('body=' + String(o.body).slice(0, 500)) : ''); } catch (e) {}
      return of.apply(this, arguments);
    };
  } catch (e) {}
  try {
    var oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (m, u) { this.__rk = { m: m, u: u }; L('xhr.open', m, u); return oo.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function (b) { try { L('xhr.send', JSON.stringify((this.__rk || {})), b ? String(b).slice(0, 500) : ''); } catch (e) {} return os.apply(this, arguments); };
  } catch (e) {}
  try {
    var ows = window.WebSocket;
    if (ows) window.WebSocket = function (u, p) { try { L('ws', u); } catch (e) {} return new ows(u, p); };
  } catch (e) {}

  // 2) 加密库边界（等库加载后再挂，轮询 3 秒）
  var t = setInterval(function () {
    try {
      if (window.CryptoJS) {
        var C = window.CryptoJS;
        ['MD5', 'SHA1', 'SHA256', 'SHA512', 'HmacMD5', 'HmacSHA1', 'HmacSHA256'].forEach(function (k) {
          if (C[k] && !C[k].__rk) {
            var o = C[k];
            var f = function () { try { L('CryptoJS.' + k, [].slice.call(arguments).map(String).join(' | ').slice(0, 600)); } catch (e) {} return o.apply(this, arguments); };
            f.__rk = 1; C[k] = f;
          }
        });
      }
      ['md5', 'sha1', 'sha256'].forEach(function (k) {
        if (window[k] && !window[k].__rk) {
          var o = window[k];
          var f = function () { try { L('win.' + k, [].slice.call(arguments).map(String).join(' | ').slice(0, 600)); } catch (e) {} return o.apply(this, arguments); };
          f.__rk = 1; window[k] = f;
        }
      });
      if (window.sparkMD5 && !window.sparkMD5.__rk) { var _s = window.sparkMD5; window.sparkMD5 = function () { L('sparkMD5'); return _s.apply(this, arguments); }; window.sparkMD5.__rk = 1; }
      if (window.crypto && window.crypto.subtle && !window.crypto.subtle.__rk) {
        var sub = window.crypto.subtle, od = sub.digest;
        sub.digest = function (alg, data) { try { L('subtle.digest', JSON.stringify(alg), String(data).slice(0, 300)); } catch (e) {} return od.apply(this, arguments); };
        sub.__rk = 1;
      }
    } catch (e) {}
  }, 30);
  setTimeout(function () { clearInterval(t); }, 3000);

  // 3) 构造边界
  try { wrap(JSON, 'stringify', 'JSON.stringify'); } catch (e) {}
  try { wrap(JSON, 'parse', 'JSON.parse'); } catch (e) {}
  try { wrap(window, 'atob', 'atob'); } catch (e) {}
  try { wrap(window, 'btoa', 'btoa'); } catch (e) {}
  L('hooked & armed');
})();
