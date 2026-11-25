/* ============================================================
 *  渲染引擎：把内容数据变成页面
 *  一般不需要改这个文件，除非你想加新的块类型
 * ============================================================ */
(function () {
  "use strict";

  var app = document.getElementById("app");
  var players = []; // 已注册的音频播放器（声明要在 buildAudio 调用之前）

  /* ---------- 小工具 ---------- */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // 支持 **加粗** 和 [文字](链接)
  function inline(s) {
    var t = esc(s);
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return t;
  }

  function paragraphs(text) {
    return String(text || "")
      .split(/\n{2,}/)
      .map(function (p) { return p.trim(); })
      .filter(Boolean)
      .map(function (p) { return "<p>" + inline(p).replace(/\n/g, "<br>") + "</p>"; })
      .join("");
  }

  function el(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  function fmtTime(sec) {
    if (!isFinite(sec) || sec < 0) sec = 0;
    var m = Math.floor(sec / 60);
    var s = Math.floor(sec % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  /* ---------- 音频播放器 ---------- */
  function buildAudio(item) {
    var wrap = el("div", "audio-item");
    wrap.innerHTML =
      '<button class="audio-btn" type="button" aria-label="播放">' +
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5.5v13l10-6.5z" fill="currentColor" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/></svg>' +
      "</button>" +
      '<div class="audio-main">' +
        '<div class="audio-title">' + esc(item.title || "录音") + "</div>" +
        (item.desc ? '<div class="audio-desc">' + esc(item.desc) + "</div>" : "") +
        '<div class="audio-bar" role="slider" aria-label="播放进度" tabindex="0">' +
          '<div class="audio-fill"></div>' +
        "</div>" +
      "</div>" +
      '<div class="audio-time">0:00</div>';

    var audio = new Audio();
    audio.preload = "metadata";
    audio.src = item.src;

    var btn = wrap.querySelector(".audio-btn");
    var bar = wrap.querySelector(".audio-bar");
    var fill = wrap.querySelector(".audio-fill");
    var time = wrap.querySelector(".audio-time");

    var ICON_PLAY = '<path d="M9 5.5v13l10-6.5z" fill="currentColor" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/>';
    var ICON_PAUSE = '<path d="M8.6 6v12M15.4 6v12" fill="none" stroke="currentColor" stroke-width="3.8" stroke-linecap="round"/>';

    function setIcon(paused) {
      btn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' +
        (paused ? ICON_PLAY : ICON_PAUSE) + "</svg>";
      btn.setAttribute("aria-label", paused ? "播放" : "暂停");
    }

    function paint() {
      var d = audio.duration;
      var p = isFinite(d) && d > 0 ? audio.currentTime / d : 0;
      fill.style.width = (p * 100).toFixed(2) + "%";
      time.textContent = audio.currentTime > 0 || !audio.paused
        ? fmtTime(audio.currentTime)
        : fmtTime(d);
    }

    btn.addEventListener("click", function () {
      if (audio.paused) {
        players.forEach(function (p) { if (p.audio !== audio && !p.audio.paused) p.audio.pause(); });
        audio.play().catch(function () {});
      } else {
        audio.pause();
      }
    });

    audio.addEventListener("play", function () { wrap.classList.add("is-playing"); setIcon(false); });
    audio.addEventListener("pause", function () { wrap.classList.remove("is-playing"); setIcon(true); });
    audio.addEventListener("ended", function () { wrap.classList.remove("is-playing"); setIcon(true); audio.currentTime = 0; paint(); });
    audio.addEventListener("loadedmetadata", paint);
    audio.addEventListener("timeupdate", paint);

    function seekFromEvent(e) {
      var rect = bar.getBoundingClientRect();
      var x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
      var r = Math.max(0, Math.min(1, x / rect.width));
      if (isFinite(audio.duration)) {
        audio.currentTime = r * audio.duration;
        fill.style.width = (r * 100).toFixed(2) + "%";
      }
    }

    var dragging = false;
    bar.addEventListener("pointerdown", function (e) {
      if (!isFinite(audio.duration)) return;
      dragging = true;
      wrap.classList.add("is-dragging");
      bar.setPointerCapture(e.pointerId);
      seekFromEvent(e);
    });
    bar.addEventListener("pointermove", function (e) { if (dragging) seekFromEvent(e); });
    bar.addEventListener("pointerup", function () {
      dragging = false;
      wrap.classList.remove("is-dragging");
      paint();
    });
    bar.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 5); }
      if (e.key === "ArrowLeft") { audio.currentTime = Math.max(0, audio.currentTime - 5); }
    });

    setIcon(true);
    players.push({ audio: audio, paint: paint });
    return wrap;
  }

  /* ---------- 页面渲染主体 ---------- */
  function boot(PAGE) {

    /* 文档信息 */
    var title = PAGE.siteTitle || "我的页面";
    document.title = title;
    var desc = PAGE.description || "";
    var metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) metaDesc.setAttribute("content", desc);
    var ogT = document.querySelector('meta[property="og:title"]');
    if (ogT) ogT.setAttribute("content", title);
    var ogD = document.querySelector('meta[property="og:description"]');
    if (ogD) ogD.setAttribute("content", desc);
    var ogI = document.querySelector('meta[property="og:image"]');
    /* 运行时覆盖 og:image 没意义（爬虫不执行 JS），反而会把静态页写好的
       绝对地址换成相对路径——原样保留，让爬虫抓到 assets/og.jpg */

    /* 首屏 */
    var hero = PAGE.hero || {};
    var heroEl = document.getElementById("hero");
    if (hero.cover) heroEl.style.backgroundImage = 'url("' + hero.cover + '")';
    var hk = document.getElementById("heroKicker");
    var ht = document.getElementById("heroTitle");
    var hs = document.getElementById("heroSub");
    var hm = document.getElementById("heroMeta");
    if (hk) hk.innerHTML = hero.kicker || "";
    if (ht) ht.textContent = hero.title || title;
    if (hs) hs.innerHTML = hero.subtitle || "";
    if (hm) hm.innerHTML = hero.meta || "";
    if (hk && !hero.kicker) hk.remove();
    if (hs && !hero.subtitle) hs.remove();
    if (hm && !hero.meta) hm.remove();

    /* 正文 */
    var content = document.getElementById("content");
    var blocks = PAGE.blocks || [];

    // Markdown 路线：content.md 经 build.py 编译成整段 HTML
    if (PAGE.html) {
      content.innerHTML = PAGE.html;
      Array.prototype.forEach.call(content.children, function (n) {
        n.classList.add("reveal");
      });
      Array.prototype.forEach.call(
        content.querySelectorAll(".block-audio[data-items]"),
        function (box) {
          JSON.parse(box.dataset.items).forEach(function (it) {
            box.appendChild(buildAudio(it));
          });
          box.removeAttribute("data-items");
        }
      );
      // 已在缓存里的图片不会触发 load 事件，手动补淡入
      Array.prototype.forEach.call(content.querySelectorAll("img"), function (im) {
        if (im.complete) im.classList.add("is-loaded");
      });
    }

    blocks.forEach(function (b) {
      if (!b || !b.type) return;
      var node = null;

      switch (b.type) {

        case "heading":
          node = el(b.level === 3 ? "h3" : "h2", "", inline(b.text));
          break;

        case "text":
          node = el("div", "block-text", paragraphs(b.text));
          break;

        case "quote":
          node = el("blockquote", "block-quote",
            inline(b.text) + (b.cite ? "<cite>" + esc(b.cite) + "</cite>" : ""));
          break;

        case "image":
          node = el("figure", "block-figure",
            '<a href="' + esc(b.src) + '" data-full="' + esc(b.src) + '" data-cap="' + esc(b.caption || "") + '">' +
              '<img src="' + esc(b.src) + '" alt="' + esc(b.alt || "") + '" loading="lazy" decoding="async">' +
            "</a>" +
            (b.caption ? "<figcaption>" + esc(b.caption).replace(/\\n/g, "<br>") + "</figcaption>" : ""));
          break;

        case "gallery":
          node = el("div", "block-gallery");
          (b.items || []).forEach(function (it) {
            var a = el("a", "");
            a.href = it.src;
            a.dataset.full = it.src;
            a.dataset.cap = it.caption || it.alt || "";
            var img = new Image();
            img.src = it.src;
            img.alt = it.alt || it.caption || "";
            img.loading = "lazy";
            img.decoding = "async";
            a.appendChild(img);
            node.appendChild(a);
          });
          break;

        case "audio":
          node = el("div", "block-audio");
          (b.items || []).forEach(function (it) { node.appendChild(buildAudio(it)); });
          break;

        case "divider":
          node = el("hr", "block-hr");
          break;

        case "links":
          node = el("div", "block-links");
          (b.items || []).forEach(function (it) {
            var a = el("a", "", esc(it.label || it.href));
            a.href = it.href;
            a.target = "_blank";
            a.rel = "noopener";
            node.appendChild(a);
          });
          break;
      }

      if (node) {
        node.classList.add("reveal");
        content.appendChild(node);
      }
    });

    /* 页脚 */
    var footer = PAGE.footer || {};
    var footerNote = document.getElementById("footerNote");
    if (footerNote) {
      footerNote.innerHTML = footer.note || "";
      if (!footer.note) footerNote.remove();
    }

    var qrbox = document.getElementById("qrbox");
    if (footer.qr && qrbox) {
      var qrImg = document.getElementById("qrImg");
      qrImg.addEventListener("load", function () { qrbox.hidden = false; });
      qrImg.addEventListener("error", function () { qrbox.hidden = true; });
      qrImg.src = footer.qr;
    }

    /* toast */
    var toast = document.getElementById("toast");
    var toastTimer = null;
    function say(msg) {
      toast.textContent = msg;
      toast.hidden = false;
      requestAnimationFrame(function () { toast.classList.add("is-on"); });
      clearTimeout(toastTimer);
      toastTimer = setTimeout(function () {
        toast.classList.remove("is-on");
        setTimeout(function () { toast.hidden = true; }, 260);
      }, 1800);
    }

    var copyBtn = document.getElementById("copyBtn");
    if (copyBtn) {
      copyBtn.addEventListener("click", function () {
        var url = location.href.split("#")[0].split("?")[0];
        if (navigator.share && /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) {
          navigator.share({ title: title, url: url }).catch(function () {});
          return;
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(function () { say("链接已复制"); },
            function () { say("复制失败，请长按地址栏"); });
        } else {
          var t = document.createElement("textarea");
          t.value = url;
          document.body.appendChild(t);
          t.select();
          try { document.execCommand("copy"); say("链接已复制"); } catch (err) { say("复制失败，请长按地址栏"); }
          t.remove();
        }
      });
    }

    /* 大图查看 */
    var lb = document.getElementById("lightbox");
    var lbImg = document.getElementById("lbImg");
    var lbCap = document.getElementById("lbCap");

    function openLightbox(src, cap) {
      lbImg.src = src;
      lbImg.alt = (cap || "").replace(/<[^>]*>/g, "").replace(/\\n/g, " ");
      // data-cap 里可能是 build 预转换好的 HTML（<br>、微信表情 <img>），按 HTML 渲染
      lbCap.innerHTML = (cap || "").replace(/\\n/g, "<br>");
      lb.hidden = false;
      document.body.style.overflow = "hidden";
      requestAnimationFrame(function () { lb.classList.add("is-open"); });
    }
    function closeLightbox() {
      lb.classList.remove("is-open");
      document.body.style.overflow = "";
      setTimeout(function () {
        lb.hidden = true;
        lbImg.removeAttribute("src");
      }, 250);
    }

    content.addEventListener("click", function (e) {
      var a = e.target.closest("a[data-full]");
      if (!a) return;
      e.preventDefault();
      openLightbox(a.dataset.full, a.dataset.cap);
    });

    lb.addEventListener("click", function (e) {
      // 点叉叉时 target 其实是里面的 svg/path，得用 closest 往上找
      if (e.target === lb || e.target.closest("#lbClose")) closeLightbox();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !lb.hidden) closeLightbox();
    });

    /* 回到最顶端：解锁前键盘/地址栏把页面顶下去一点，等布局稳定再纠正，
       否则首屏一上来就是"已经缩上去"的状态，得往上拉才有回弹效果 */
    resetToTop();

    /* 进场动画 */
    var reveals = document.querySelectorAll(".reveal");    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            en.target.classList.add("is-in");
            io.unobserve(en.target);
          }
        });
      }, { rootMargin: "0px 0px -8% 0px", threshold: 0.06 });
      reveals.forEach(function (r) { io.observe(r); });
    } else {
      reveals.forEach(function (r) { r.classList.add("is-in"); });
    }

    /* 阅读进度 */
    var bar = document.getElementById("progressBar");
    var ticking = false;
    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        var h = document.documentElement;
        var max = h.scrollHeight - h.clientHeight;
        var p = max > 0 ? h.scrollTop / max : 0;
        bar.style.transform = "scaleX(" + Math.min(1, Math.max(0, p)) + ")";
        ticking = false;
      });
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---------- 图片淡入（捕获阶段接收不冒泡的 load） ---------- */
  document.addEventListener("load", function (e) {
    var t = e.target;
    if (t && t.tagName === "IMG") t.classList.add("is-loaded");
  }, true);

  /* ---------- 返回顶部 ---------- */
  var toTop = document.getElementById("toTop");
  if (toTop) {
    var heroEl = document.getElementById("hero");
    window.addEventListener("scroll", function () {
      toTop.classList.toggle("is-show",
        window.scrollY > (heroEl ? heroEl.offsetHeight * 0.5 : 600));
    }, { passive: true });
    toTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  /* ---------- 收起加载动画 ---------- */
  function hideLoader() {
    var bl = document.getElementById("bootLoader");
    if (bl) { bl.classList.add("is-done"); setTimeout(function () { bl.remove(); }, 350); }
  }

  /* ---------- 回到最顶端 ---------- */
  // html 上有 scroll-behavior:smooth，直接 scrollTo 会变成动画，动画途中
  // 页面还在长高（懒加载图片、字体替换），经常停在半路。这里临时关掉平滑过渡。
  // 只纠正"贴近顶部"的小偏移：用户已经开始往下读就别抢滚动。
  function resetToTop() {
    function jump() {
      if (window.scrollY > 200) return;
      var h = document.documentElement;
      var prev = h.style.scrollBehavior;
      h.style.scrollBehavior = "auto";
      window.scrollTo(0, 0);
      h.style.scrollBehavior = prev;
    }
    jump();
    requestAnimationFrame(jump);
    setTimeout(jump, 120);
    setTimeout(jump, 450);
  }

  /* ---------- 入口 ---------- */
  // 刷新后总是回到顶部：加密页是异步渲染的，浏览器记忆的滚动位置
  // 会套在"还没长高"的页面上，恢复出错误的偏移
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  window.scrollTo(0, 0);

  var stub = window.PAGE;

  if (!stub) {
    app.innerHTML = '<div style="padding:3rem 1.5rem;font-family:sans-serif;">' +
      '<h2>没有找到内容</h2><p>请检查 content.js 是否存在。</p></div>';
    hideLoader();
    return;
  }

  window.__hideLoader = hideLoader;

  if (stub.locked && window.__unlock) {
    window.__unlock(stub, boot);
  } else {
    boot(stub);
    hideLoader();
  }
})();
