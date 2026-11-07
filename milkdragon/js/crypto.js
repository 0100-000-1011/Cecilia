/* ============================================================
 *  加密子页面的解锁模块
 *  流程：读 access.json（盐/迭代/校验哈希）→ 校验缓存的密钥
 *  （每次进入页面都会和云端哈希重新比对，密码改了缓存即失效）
 *  → 不匹配则弹密码框 → 派生 AES 密钥 → 解密 enc/page.enc 与
 *  enc/assets/*.enc → 生成 blob 链接交给渲染引擎
 * ============================================================ */
(function () {
  "use strict";

  var storeKey = "qrpage:key:" + location.pathname;
  var isLocal = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);

  /* ---------- 编码小工具 ---------- */
  function bufToHex(buf) {
    var v = new Uint8Array(buf), s = "";
    for (var i = 0; i < v.length; i++) s += ("0" + v[i].toString(16)).slice(-2);
    return s;
  }
  function hexToBuf(hex) {
    var out = new Uint8Array(hex.length / 2);
    for (var i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
    return out;
  }
  function b64ToBuf(b64) {
    var bin = atob(b64), out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  function subtle() {
    if (!window.crypto || !window.crypto.subtle) {
      throw new Error("此环境不支持 Web Crypto，请通过 https 或 localhost 访问");
    }
    return window.crypto.subtle;
  }

  async function sha256Hex(data) {
    return bufToHex(await subtle().digest("SHA-256", data));
  }

  async function deriveRaw(pw, saltB64, iter) {
    var km = await subtle().importKey(
      "raw", new TextEncoder().encode(pw), "PBKDF2", false, ["deriveBits"]);
    return await subtle().deriveBits(
      { name: "PBKDF2", hash: "SHA-256", salt: b64ToBuf(saltB64), iterations: iter },
      km, 256);
  }

  async function fetchJSON(url) {
    var r = await fetch(url + "?t=" + Date.now(), { cache: "no-store" });
    if (!r.ok) throw new Error("无法读取 " + url);
    return r.json();
  }

  async function decryptFile(url, raw) {
    var r = await fetch(url);
    if (!r.ok) throw new Error("无法读取 " + url);
    var data = new Uint8Array(await r.arrayBuffer());
    var key = await subtle().importKey("raw", raw, "AES-GCM", false, ["decrypt"]);
    var plain = await subtle().decrypt({ name: "AES-GCM", iv: data.slice(0, 12) },
      key, data.slice(12));
    return new Uint8Array(plain);
  }

  /* ---------- 锁屏 ---------- */
  var els = {};

  function showLock() {
    els.lock.hidden = false;
    requestAnimationFrame(function () { els.lock.classList.add("is-open"); });
    setTimeout(function () { els.input.focus(); }, 350);
  }
  function hideLock() {
    els.lock.classList.remove("is-open");
    setTimeout(function () { els.lock.hidden = true; }, 300);
  }
  function lockMsg(text, bad) {
    els.err.textContent = text;
    els.err.hidden = !text;
    els.err.classList.toggle("is-bad", !!bad);
  }
  function lockBusy(on) {
    els.btn.disabled = on;
    els.input.disabled = on;
    els.btn.textContent = on ? "验证中…" : "解锁";
  }
  function shake() {
    els.card.classList.remove("is-shake");
    void els.card.offsetWidth;
    els.card.classList.add("is-shake");
  }

  function tryPassword(pw, access) {
    lockBusy(true);
    return deriveRaw(pw, access.salt, access.iter)
      .then(function (raw) {
        return sha256Hex(raw).then(function (hex) {
          if (hex !== access.verifier) throw new Error("bad");
          return raw;
        });
      })
      .then(function (raw) {
        localStorage.setItem(storeKey, bufToHex(raw));
        lockBusy(false);
        return raw;
      })
      .catch(function (e) {
        lockBusy(false);
        if (e && e.message === "bad") {
          lockMsg("密码不对，再试一次", true);
          shake();
          els.input.select();
          return null;
        }
        throw e;
      });
  }

  function promptLoop(access) {
    return new Promise(function (resolve) {
      showLock();
      els.form.onsubmit = function (ev) {
        ev.preventDefault();
        var pw = els.input.value;
        if (!pw) { lockMsg("请输入密码", true); return; }
        tryPassword(pw, access).then(function (raw) { if (raw) resolve(raw); });
      };
    });
  }

  /* ---------- 解锁主流程 ---------- */
  window.__unlock = function (stub, cb) {
    els = {
      lock: document.getElementById("lock"),
      card: document.getElementById("lockCard"),
      form: document.getElementById("lockForm"),
      input: document.getElementById("lockInput"),
      btn: document.getElementById("lockBtn"),
      err: document.getElementById("lockErr"),
      status: document.getElementById("lockStatus")
    };

    function fail(msg) {
      showLock();
      lockBusy(false);
      els.btn.textContent = "重试";
      els.form.onsubmit = function (ev) { ev.preventDefault(); location.reload(); };
      lockMsg(msg, true);
    }

    fetchJSON("access.json").then(function (access) {
      if (!access) {
        fail("没有找到 access.json —— 请先运行 python3 build.py 并部署");
        return;
      }
      if (!access.protected) { cb(stub); return; }

      // 密码缓存只在本地；每次进入都和云端哈希重新比对
      var cached = localStorage.getItem(storeKey);

      var ready;
      if (cached) {
        ready = sha256Hex(hexToBuf(cached)).then(function (hex) {
          if (hex !== access.verifier) {
            // 密码已更换：清掉旧缓存，重新询问
            localStorage.removeItem(storeKey);
            return promptLoop(access);
          }
          return hexToBuf(cached);
        });
      } else {
        ready = promptLoop(access);
      }

      // 本地调试快捷方式：localhost 下可用 ?__pw=密码 跳过输入框
      var qp = isLocal ? new URLSearchParams(location.search).get("__pw") : null;
      if (qp) {
        ready = tryPassword(qp, access).then(function (raw) {
          if (!raw) throw new Error("调试密码错误");
          return raw;
        });
      }

      ready.then(function (raw) { return decryptAll(raw); })
        .then(function (page) { hideLock(); cb(page); })
        .catch(function (e) {
          console.error(e);
          fail("解密失败：" + (e && e.message ? e.message : "未知错误"));
        });
    }, function () {
      fail("没有找到 access.json —— 请先运行 python3 build.py 并部署");
    });

    function decryptAll(raw) {
      els.status.hidden = false;
      els.status.textContent = "解密中…";
      return decryptFile("enc/page.enc", raw).then(function (plain) {
        var page = JSON.parse(new TextDecoder().decode(plain));
        var manifest = page.manifest || [];
        var map = {};

        function next(i) {
          if (i >= manifest.length) {
            var html = page.html || "";
            Object.keys(map).forEach(function (p) {
              html = html.split(p).join(map[p]);
            });
            page.html = html;
            if (page.hero && map[page.hero.cover]) {
              page.hero.cover = map[page.hero.cover];
            }
            els.status.textContent = "完成";
            return page;
          }
          var e = manifest[i];
          return decryptFile(e.f, raw).then(function (buf) {
            map[e.p] = URL.createObjectURL(new Blob([buf], { type: e.t }));
            els.status.textContent = "解密中… " + (i + 1) + "/" + manifest.length;
            return next(i + 1);
          });
        }
        return next(0);
      });
    }
  };
})();
