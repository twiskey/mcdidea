/* 麦当劳点餐台 · 前端状态机
   S0 点餐 → S1 取餐号 → S2 生成中 → S3 光谱 + 旋律 */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const state = {
    menu: null,
    cart: new Map(),       // code -> qty
    order: null,
    style: "minyue",
    portraits: {},         // style -> payload
    share: null,           // 当前用于分享的 payload
    pregen: null,
    loadTimer: null,
  };

  const money = (n) => "¥" + Number(n).toFixed(2);

  async function api(path, body) {
    const opt = body === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    };
    let res;
    try {
      res = await fetch(path, opt);
    } catch (e) {
      throw new Error("网络断了，请检查后再试");
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "服务开小差了");
    return data;
  }

  /* ---------------------------------------------------------- 视图切换 */
  function show(view) {
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("is-active"));
    $(view).classList.add("is-active");
    document.body.dataset.view = view;
    window.scrollTo(0, 0);
  }

  let toastTimer = null;
  function toast(msg) {
    const el = $("toast");
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 1800);
  }

  /* ---------------------------------------------------------- S0 菜单 */
  async function loadMenu() {
    try {
      state.menu = await api("/api/menu");
      renderStore();
      renderTabs();
      renderMenu(state.menu.categories[0].key);
      updateCart();
    } catch (e) {
      $("menuList").innerHTML = `<p class="group-title">菜单加载失败：${e.message}</p>`;
    }
  }

  // 门店条：开启点餐台时由 MCP 缓存提供的最近门店
  function renderStore() {
    const el = $("storeLine");
    const st = state.menu.store;
    if (!st) {
      el.textContent = "本地快照 · 未同步门店";
      return;
    }
    const km = st.distance >= 1000 ? `${(st.distance / 1000).toFixed(1)}km` : `${st.distance}m`;
    const open = st.open_now ? "营业中" : "未营业";
    const when = state.menu.synced_at ? state.menu.synced_at.slice(5, 16).replace("T", " ") : "";
    const short = st.name.replace(/^麦当劳/, "");
    el.textContent = `${short} · ${km} · ${open} · 菜单已同步 ${when}`;
    el.title = st.address || "";
  }

  function renderTabs() {
    const tabs = $("tabs");
    tabs.innerHTML = "";
    state.menu.categories.forEach((c, i) => {
      const b = document.createElement("button");
      b.className = "tab" + (i === 0 ? " is-active" : "");
      b.textContent = c.label;
      b.dataset.cat = c.key;
      b.onclick = () => {
        tabs.querySelectorAll(".tab").forEach((t) => t.classList.remove("is-active"));
        b.classList.add("is-active");
        renderMenu(c.key);
      };
      tabs.appendChild(b);
    });
  }

  function renderMenu(catKey) {
    const cat = state.menu.categories.find((c) => c.key === catKey);
    const list = $("menuList");
    list.innerHTML = "";
    const title = document.createElement("p");
    title.className = "group-title";
    title.textContent = cat.label + " · " + cat.items.length + " 款";
    list.appendChild(title);

    cat.items.forEach((it) => {
      const card = document.createElement("article");
      card.className = "item";
      card.dataset.code = it.code;
      card.innerHTML = `
        <div class="thumb" style="--c:${it.color}"><span>${it.initial}</span></div>
        <div class="item-main">
          <h3>${it.name}</h3>
          <p>${Math.round(it.kcal)} kcal · 蛋白质 ${it.protein}g</p>
          <div class="item-bottom"><span class="price">${it.price.toFixed(2)}</span></div>
        </div>
        <div class="stepper"></div>`;
      list.appendChild(card);
      paintStepper(it);
    });
  }

  function paintStepper(it) {
    const card = document.querySelector(`.item[data-code="${it.code}"]`);
    if (!card) return;
    const box = card.querySelector(".stepper");
    const qty = state.cart.get(it.code) || 0;
    if (!qty) {
      box.innerHTML = `<button class="step-btn add" aria-label="加入 ${it.name}">+</button>`;
      box.querySelector("button").onclick = () => changeQty(it, 1);
    } else {
      box.innerHTML = `
        <button class="step-btn" aria-label="减少">−</button>
        <span class="qty">${qty}</span>
        <button class="step-btn add" aria-label="增加">+</button>`;
      const [minus, plus] = box.querySelectorAll("button");
      minus.onclick = () => changeQty(it, -1);
      plus.onclick = () => changeQty(it, 1);
    }
  }

  function changeQty(it, delta) {
    const now = (state.cart.get(it.code) || 0) + delta;
    if (now <= 0) state.cart.delete(it.code);
    else state.cart.set(it.code, Math.min(now, 20));
    paintStepper(it);
    updateCart();
  }

  function cartSummary() {
    let count = 0, total = 0;
    if (state.menu) {
      state.menu.categories.forEach((c) => c.items.forEach((it) => {
        const q = state.cart.get(it.code) || 0;
        if (q) { count += q; total += q * it.price; }
      }));
    }
    return { count, total };
  }

  function updateCart() {
    const { count, total } = cartSummary();
    $("cartCount").textContent = count + " 件";
    $("cartTotal").textContent = money(total);
    $("btnOrder").disabled = count === 0;
  }

  /* ---------------------------------------------------------- 下单 */
  async function submitOrder() {
    const items = [];
    state.cart.forEach((qty, code) => items.push({ code, qty }));
    if (!items.length) return;
    const btn = $("btnOrder");
    btn.disabled = true;
    btn.textContent = "提交中…";
    try {
      const rec = await api("/api/order", { items });
      state.order = rec;
      state.portraits = {};
      state.pregen = null;
      renderPickup(rec);
      show("view-pickup");
      // 后台预生成默认曲风，用户点"想看"时几乎即时
      setTimeout(pregen, 350);
    } catch (e) {
      toast(e.message);
    } finally {
      btn.disabled = state.cart.size === 0;
      btn.textContent = "下单";
    }
  }

  function renderPickup(rec) {
    $("pickupNo").textContent = rec.pickup;
    const box = $("receipt");
    box.innerHTML = "";
    rec.items.forEach((r) => {
      const row = document.createElement("div");
      row.className = "r-line";
      row.innerHTML = `<span class="r-name">${r.name}${r.qty > 1 ? `<span class="r-qty">×${r.qty}</span>` : ""}</span>
                       <span>${money(r.price)}</span>`;
      box.appendChild(row);
    });
    const total = document.createElement("div");
    total.className = "r-line total";
    total.innerHTML = `<span>合计 · ${rec.count} 件</span><span>${money(rec.total)}</span>`;
    box.appendChild(total);
    $("askCard").hidden = false;
    $("btnRelink").hidden = true;
  }

  function pregen() {
    if (!state.order || state.pregen) return state.pregen;
    state.pregen = api("/api/portrait", { order_no: state.order.order_no, style: "minyue" })
      .then((d) => { state.portraits[d.style] = d; return d; })
      .catch(() => null);
    return state.pregen;
  }

  /* ---------------------------------------------------------- S2/S3 */
  function startLoading() {
    const subs = ["解析营养数据…", "绘制营养光谱…", "编排营养旋律…"];
    let i = 0;
    $("loadSub").textContent = subs[0];
    $("loading").hidden = false;
    clearInterval(state.loadTimer);
    state.loadTimer = setInterval(() => {
      i = (i + 1) % subs.length;
      $("loadSub").textContent = subs[i];
    }, 750);
  }

  function stopLoading() {
    clearInterval(state.loadTimer);
    $("loading").hidden = true;
  }

  async function openPortrait() {
    if (!state.order) return;
    show("view-portrait");
    $("topPickup").textContent = state.order.pickup;
    if (state.portraits[state.style]) {
      renderPortrait(state.portraits[state.style]);
      return;
    }
    startLoading();
    try {
      const d = state.pregen
        ? await state.pregen.then((x) => x || fetchPortrait(state.style))
        : await fetchPortrait(state.style);
      renderPortrait(d);
    } catch (e) {
      toast(e.message);
      show("view-pickup");
    } finally {
      stopLoading();
    }
  }

  async function fetchPortrait(style) {
    const d = await api("/api/portrait", { order_no: state.order.order_no, style });
    state.portraits[style] = d;
    return d;
  }

  function renderPortrait(d) {
    state.style = d.style;
    state.share = d;
    $("topPickup").textContent = d.pickup;
    $("spectrumImg").src = d.spectrum_url;
    $("lbImg").src = d.spectrum_url;

    document.querySelectorAll(".seg-btn").forEach((b) => {
      b.classList.toggle("is-active", b.dataset.style === d.style);
    });

    const m = d.melody;
    const plain = $("plain");
    plain.innerHTML = "";
    // 只保留大众版的第一行（粗体的一句话），其余概括不再显示
    const leadLine = (m.plain || "").split("\n").map((s) => s.trim())
      .find((s) => /^\*{0,2}一句话/.test(s)) || "";
    const lead = leadLine.replace(/\*\*/g, "").replace(/^一句话[:：]\s*/, "").trim();
    if (lead) {
      const p = document.createElement("p");
      p.className = "lead";
      p.textContent = lead;
      plain.appendChild(p);
    }

    $("footnote").textContent =
      `${d.style_label} · ${m.music.bpm} BPM · ${m.music.duration}s · ` +
      `糖为推算值（碳水×0.35）`;

    const audio = $("audio");
    audio.src = d.audio_url;
    audio.currentTime = 0;
    paintProgress();
    $("playBtn").setAttribute("aria-label", "播放");
    $("iconPlay").hidden = false;
    $("iconPause").hidden = true;
  }

  async function switchStyle(style) {
    if (style === state.style && state.portraits[style]) return;
    const btns = document.querySelectorAll(".seg-btn");
    btns.forEach((b) => { b.disabled = true; });
    const target = document.querySelector(`.seg-btn[data-style="${style}"]`);
    const old = target.textContent;
    target.textContent = "生成中";
    try {
      const d = state.portraits[style] || await fetchPortrait(style);
      renderPortrait(d);
      $("audio").pause();
    } catch (e) {
      toast(e.message);
    } finally {
      btns.forEach((b) => { b.disabled = false; });
      target.textContent = old;
    }
  }

  /* ---------------------------------------------------------- 播放器 */
  function fmt(sec) {
    if (!isFinite(sec)) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  }

  function paintProgress() {
    const a = $("audio");
    const d = a.duration || 0;
    const p = d ? (a.currentTime / d) * 100 : 0;
    $("fill").style.width = p + "%";
    $("knob").style.left = p + "%";
    $("time").textContent = `${fmt(a.currentTime)} / ${fmt(d)}`;
  }

  function bindPlayer() {
    const a = $("audio");
    $("playBtn").onclick = () => {
      if (!a.src) return;
      if (a.paused) {
        a.play().then(() => {
          $("iconPlay").hidden = true;
          $("iconPause").hidden = false;
        }).catch(() => toast("先点一下播放按钮试试"));
      } else {
        a.pause();
      }
    };
    a.addEventListener("play", () => {
      $("iconPlay").hidden = true;
      $("iconPause").hidden = false;
    });
    a.addEventListener("pause", () => {
      $("iconPlay").hidden = false;
      $("iconPause").hidden = true;
    });
    a.addEventListener("timeupdate", paintProgress);
    a.addEventListener("loadedmetadata", paintProgress);
    a.addEventListener("ended", () => {
      $("iconPlay").hidden = false;
      $("iconPause").hidden = true;
      paintProgress();
    });
    $("track").addEventListener("click", (ev) => {
      const r = ev.currentTarget.getBoundingClientRect();
      const ratio = Math.min(Math.max((ev.clientX - r.left) / r.width, 0), 1);
      if (a.duration) { a.currentTime = ratio * a.duration; paintProgress(); }
    });
  }

  /* ---------------------------------------------------------- 分享 */
  function shareInfo(d) {
    const r = (d.melody && d.melody.rates) || {};
    const keys = Object.keys(r);
    const top = keys.length ? keys.reduce((a, b) => (r[a] >= r[b] ? a : b)) : "";
    return { top, pct: top ? Math.round(r[top] * 100) : 0, kcal: Math.round(d.nutrition.kcal) };
  }

  function shareText(d, withTags) {
    const { top, pct, kcal } = shareInfo(d);
    let t = `【${d.pickup}】${kcal} kcal 的一餐，营养光谱出来了：${top}最突出（${pct}%）。` +
            "这是属于我的这一刻的味道。";
    if (withTags) t += "\n#麦当劳 #营养光谱 #今天吃什么";
    return t;
  }

  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (e) { /* 落到 execCommand */ }
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.top = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return ok;
    } catch (e) {
      return false;
    }
  }

  async function saveImage(d) {
    const res = await fetch(d.spectrum_url);
    if (!res.ok) throw new Error("下载失败");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `营养光谱_${d.pickup}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 3000);
  }

  function openShare() {
    if (!state.share) return;
    const d = state.share;
    const { top, pct, kcal } = shareInfo(d);
    $("shareSub").textContent = `${d.pickup} · ${kcal} kcal · ${top}最突出 ${pct}%`;
    $("shareMask").hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeShare() {
    $("shareMask").hidden = true;
    document.body.style.overflow = "";
  }

  async function doShare(act) {
    const d = state.share;
    if (!d) return;
    if (act === "save") {
      closeShare();
      try {
        await saveImage(d);
        toast("光谱图已保存，去 App 里选图发布");
      } catch (e) {
        toast("保存失败，可长按图片另存");
      }
      return;
    }
    if (act === "wechat") {
      const ok = await copyText(shareText(d, false));
      closeShare();
      toast(ok ? "文案已复制，去微信粘贴给好友" : "复制失败，请手动选择文字");
      return;
    }
    if (act === "xhs") {
      const ok = await copyText(shareText(d, true));
      closeShare();
      toast(ok ? "文案已复制，打开小红书粘贴发布" : "复制失败，请手动选择文字");
      return;
    }
    if (act === "copy") {
      const ok = await copyText(shareText(d, true));
      closeShare();
      toast(ok ? "文案已复制" : "复制失败，请手动选择文字");
    }
  }

  /* ---------------------------------------------------------- 事件 */
  function resetAll() {
    state.cart.clear();
    state.order = null;
    state.portraits = {};
    state.share = null;
    state.pregen = null;
    state.style = "minyue";
    $("audio").pause();
    $("audio").removeAttribute("src");
    if (state.menu) {
      document.querySelectorAll(".item").forEach((card) => {
        const it = state.menu.categories.flatMap((c) => c.items)
          .find((x) => String(x.code) === card.dataset.code);
        if (it) paintStepper(it);
      });
    }
    updateCart();
    show("view-menu");
  }

  function bind() {
    $("btnOrder").onclick = submitOrder;
    $("btnYes").onclick = openPortrait;
    $("btnRelink").onclick = openPortrait;
    $("btnNo").onclick = () => {
      $("askCard").hidden = true;
      $("btnRelink").hidden = false;
      toast("好的，凭取餐号取餐");
    };
    $("btnBack").onclick = () => { $("audio").pause(); show("view-pickup"); };
    $("btnRestart").onclick = resetAll;
    $("btnNewOrder").onclick = resetAll;
    const openLb = () => {
      $("lightbox").hidden = false;
      document.body.style.overflow = "hidden";
    };
    const closeLb = () => {
      $("lightbox").hidden = true;
      document.body.style.overflow = "";
    };
    $("btnZoom").onclick = openLb;
    $("spectrumImg").onclick = openLb;
    $("lbClose").onclick = closeLb;
    $("lightbox").onclick = (ev) => {
      if (ev.target.id === "lightbox" || ev.target.classList.contains("lb-scroll")) closeLb();
    };
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && !$("lightbox").hidden) closeLb();
    });
    document.querySelectorAll(".seg-btn").forEach((b) => {
      b.onclick = () => switchStyle(b.dataset.style);
    });
    $("btnShare").onclick = openShare;
    $("shareCancel").onclick = closeShare;
    $("shareMask").onclick = (ev) => {
      if (ev.target.id === "shareMask") closeShare();
    };
    document.querySelectorAll(".share-item").forEach((b) => {
      b.onclick = () => doShare(b.dataset.act);
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") closeShare();
    });
    bindPlayer();
  }

  /* 演示入口：/?demo=1 自动下一单并打开光谱页（方便快速看效果） */
  async function demoFlow() {
    ["1406", "4437", "3755"].forEach((c) => state.cart.set(c, 1));
    if (state.menu) {
      document.querySelectorAll(".item").forEach((card) => {
        const it = state.menu.categories.flatMap((c) => c.items)
          .find((x) => String(x.code) === card.dataset.code);
        if (it) paintStepper(it);
      });
    }
    updateCart();
    await submitOrder();
    await openPortrait();
  }

  bind();
  loadMenu().then(() => {
    if (new URLSearchParams(location.search).get("demo") === "1") demoFlow();
  });
})();
