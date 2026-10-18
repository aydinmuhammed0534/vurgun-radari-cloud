(function () {
  "use strict";

  let currentFilter = "all";
  let allDeals = [];
  let settingsLoaded = false;

  const dealsGrid = document.getElementById("deals-grid");
  const statTotal = document.getElementById("stat-total");
  const statMaxProfit = document.getElementById("stat-max-profit");
  const statMaxProfitItem = document.getElementById("stat-max-profit-item");
  const statMaxDiscount = document.getElementById("stat-max-discount");
  const statNtfyTopic = document.getElementById("stat-ntfy-topic");
  const statTgStatus = document.getElementById("stat-tg-status");
  const scanStatusBadge = document.getElementById("scan-status-badge");

  const inpTopic = document.getElementById("inp-topic");
  const inpTgToken = document.getElementById("inp-tg-token");
  const inpTgChat = document.getElementById("inp-tg-chat");
  const inpMinDisc = document.getElementById("inp-min-disc");
  const inpMinProfit = document.getElementById("inp-min-profit");
  const inpAffTag = document.getElementById("inp-aff-tag");
  const inpHbAff = document.getElementById("inp-hb-aff");
  const inpSearch = document.getElementById("inp-search");
  const inpIgUser = document.getElementById("inp-ig-user");
  const inpIgPass = document.getElementById("inp-ig-pass");
  const chkIgAutopost = document.getElementById("chk-ig-autopost");

  function showToast(message) {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function () {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 4200);
  }

  function formatTL(val) {
    const num = Math.round(Number(val) || 0);
    return num.toLocaleString("tr-TR") + " TL";
  }

  function createEl(tag, className, text) {
    const el = document.createElement(tag);
    if (className) {
      el.className = className;
    }
    if (text !== undefined && text !== null) {
      el.textContent = String(text);
    }
    return el;
  }

  function renderDeals() {
    dealsGrid.replaceChildren();
    const query = (inpSearch.value || "").trim().toLowerCase();

    const filtered = allDeals.filter(function (d) {
      if (!query) return true;
      const hay = (
        (d.title || "") +
        " " +
        (d.category || "") +
        " " +
        (d.cheapest_merchant || "")
      ).toLowerCase();
      return hay.indexOf(query) !== -1;
    });

    if (filtered.length === 0) {
      const emptyCard = createEl(
        "div",
        "deal-card",
        "Tarama devam ediyor veya bu filtreye uygun fırsat henüz düşmedi. 'Şimdi Tara' butonuna basabilirsin."
      );
      dealsGrid.appendChild(emptyCard);
      return;
    }

    filtered.forEach(function (deal) {
      const card = createEl("article", "deal-card");

      const topBlock = createEl("div");
      const dealTop = createEl("div", "deal-top");
      const catBadge = createEl(
        "span",
        "badge-cat",
        (deal.category || "Elektronik") + " • " + (deal.deal_type || "FIRSAT")
      );
      const discBadge = createEl(
        "span",
        "badge-discount",
        "%" + Number(deal.discount_pct || 0).toFixed(1) + " Avantaj"
      );
      dealTop.appendChild(catBadge);
      dealTop.appendChild(discBadge);
      topBlock.appendChild(dealTop);

      const titleEl = createEl("h3", "deal-title", deal.title || "Fırsat Ürünü");
      titleEl.style.marginTop = "10px";
      topBlock.appendChild(titleEl);
      card.appendChild(topBlock);

      const priceBox = createEl("div", "price-box");

      const buyRow = createEl("div", "price-row");
      buyRow.appendChild(
        createEl("span", "", "🛒 En Ucuz (" + (deal.cheapest_merchant || "Mağaza") + "):")
      );
      buyRow.appendChild(
        createEl(
          "span",
          "price-buy",
          deal.cheapest_price > 0 ? formatTL(deal.cheapest_price) : "Linkte Gör"
        )
      );
      priceBox.appendChild(buyRow);

      if (deal.second_price > deal.cheapest_price) {
        const secRow = createEl("div", "price-row");
        secRow.appendChild(
          createEl(
            "span",
            "",
            "📊 2. En Ucuz (" + (deal.second_merchant || "Piyasa") + "):"
          )
        );
        secRow.appendChild(createEl("span", "price-second", formatTL(deal.second_price)));
        priceBox.appendChild(secRow);
      }

      if (deal.estimated_profit_tl > 0) {
        const profitBanner = createEl("div", "profit-banner");
        profitBanner.appendChild(
          createEl(
            "span",
            "",
            "💸 Al-Sat Hedefi: " + formatTL(deal.suggested_resell_price)
          )
        );
        profitBanner.appendChild(
          createEl(
            "span",
            "",
            "Net Kâr: +" +
              formatTL(deal.estimated_profit_tl) +
              " (%" +
              Math.round(deal.roi_pct || 0) +
              ")"
          )
        );
        priceBox.appendChild(profitBanner);
      }

      card.appendChild(priceBox);

      const actionsRow1 = createEl("div", "card-actions");

      const buyLink = createEl("a", "btn btn-primary", "🛒 Hemen Kap");
      const safeUrl =
        typeof deal.affiliate_url === "string" &&
        deal.affiliate_url.indexOf("https://") === 0
          ? deal.affiliate_url
          : "#";
      buyLink.setAttribute("href", safeUrl);
      buyLink.setAttribute("target", "_blank");
      buyLink.setAttribute("rel", "noopener noreferrer");

      const xLink = createEl("a", "btn btn-secondary", "𝕏 Tweet At");
      const safeXUrl =
        typeof deal.x_tweet_url === "string" &&
        deal.x_tweet_url.indexOf("https://x.com/") === 0
          ? deal.x_tweet_url
          : "#";
      xLink.setAttribute("href", safeXUrl);
      xLink.setAttribute("target", "_blank");
      xLink.setAttribute("rel", "noopener noreferrer");

      const tgBtn = createEl("button", "btn btn-accent", "📢 TG'ye At");
      tgBtn.setAttribute("title", "Bu fırsatı Telegram Kanalına gönder");
      tgBtn.addEventListener("click", function () {
        sendDealToTelegram(deal.id);
      });

      actionsRow1.appendChild(buyLink);
      actionsRow1.appendChild(xLink);
      actionsRow1.appendChild(tgBtn);
      card.appendChild(actionsRow1);

      const actionsRow2 = createEl("div", "card-actions");

      const copyBtn = createEl("button", "btn btn-secondary", "📋 Affiliate Metni");
      copyBtn.addEventListener("click", function () {
        if (navigator.clipboard && deal.share_text) {
          navigator.clipboard.writeText(deal.share_text);
          showToast("✅ Affiliate mesajı kopyalandı! Forum, WhatsApp veya Telegram'a yapıştır.");
        }
      });

      const resellBtn = createEl("button", "btn btn-secondary", "🏷️ Al-Sat İlanı Kopyala");
      resellBtn.addEventListener("click", function () {
        if (navigator.clipboard && deal.resell_text) {
          navigator.clipboard.writeText(deal.resell_text);
          showToast("💸 Sahibinden / Dolap hazır Al-Sat ilan başlığı ve açıklaması kopyalandı!");
        }
      });

      const ntfyBtn = createEl("button", "btn btn-secondary", "📲 ntfy");
      ntfyBtn.setAttribute("title", "Telefonuma ntfy bildirimi gönder");
      ntfyBtn.addEventListener("click", function () {
        sendDealToPhone(deal.id);
      });

      const mediaBtn = createEl("button", "btn btn-accent", "🎬 Story & Reels");
      mediaBtn.setAttribute("title", "Bu fırsat için Instagram Story ve Reels videosu oluştur");
      mediaBtn.addEventListener("click", async function () {
        mediaBtn.disabled = true;
        mediaBtn.textContent = "⏳ Hazırlanıyor...";
        try {
          const resp = await fetch("/api/generate-media?id=" + encodeURIComponent(deal.id));
          const resData = await resp.json();
          if (resData.ok) {
            showToast("✅ Instagram Story & Reels videosu hazırlandı!");
            window.open(resData.story_url, "_blank");
            window.open(resData.reels_url, "_blank");
          } else {
            showToast("❌ Medya oluşturulamadı: " + (resData.error || "Hata"));
          }
        } catch (e) {
          showToast("❌ Sunucu hatası");
        } finally {
          mediaBtn.disabled = false;
          mediaBtn.textContent = "🎬 Story & Reels";
        }
      });

      const igBtn = createEl("button", "btn btn-secondary", "📸 IG Reels Paylaş");
      igBtn.setAttribute("title", "Bu fırsatı Instagram Reels & Story olarak hesabına paylaş");
      igBtn.addEventListener("click", async function () {
        igBtn.disabled = true;
        igBtn.textContent = "⏳ Paylaşılıyor...";
        try {
          const resp = await fetch("/api/post-instagram", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ deal_id: deal.id, type: "reel" })
          });
          const resData = await resp.json();
          if (resData.ok) {
            showToast("🎉 Instagram Reels hesabına başarıyla yüklendi!");
          } else {
            showToast("❌ Instagram Hatası: " + (resData.error || "Giriş bilgisi gerekli"));
          }
        } catch (e) {
          showToast("❌ Bağlantı hatası");
        } finally {
          igBtn.disabled = false;
          igBtn.textContent = "📸 IG Reels Paylaş";
        }
      });

      actionsRow2.appendChild(copyBtn);
      actionsRow2.appendChild(resellBtn);
      actionsRow2.appendChild(ntfyBtn);
      actionsRow2.appendChild(mediaBtn);
      actionsRow2.appendChild(igBtn);
      card.appendChild(actionsRow2);

      dealsGrid.appendChild(card);
    });
  }

  function updateStats(deals, settings, scanState) {
    statTotal.textContent = String(deals.length);

    let maxProfit = 0;
    let maxProfitTitle = "Henüz hesaplanmadı";
    let maxDisc = 0;

    deals.forEach(function (d) {
      const p = Number(d.estimated_profit_tl || 0);
      const disc = Number(d.discount_pct || 0);
      if (p > maxProfit) {
        maxProfit = p;
        maxProfitTitle = d.title || "";
      }
      if (disc > maxDisc) {
        maxDisc = disc;
      }
    });

    statMaxProfit.textContent = "+" + formatTL(maxProfit);
    statMaxProfitItem.textContent = maxProfitTitle;
    statMaxDiscount.textContent = "%" + maxDisc.toFixed(1);
    statNtfyTopic.textContent = "ntfy: " + (settings.ntfy_topic || "-");

    if (settings.telegram_configured === "1") {
      statTgStatus.textContent =
        "✅ Telegram Kanalı Aktif (" + (settings.telegram_chat_id || "") + ")";
    } else {
      statTgStatus.textContent =
        "📢 Telegram Kanalı: Ayarpanelinden Token & Kanal ID gir";
    }

    if (!settingsLoaded && settings.ntfy_topic) {
      inpTopic.value = settings.ntfy_topic || "";
      inpTgToken.value = settings.telegram_bot_token || "";
      inpTgChat.value = settings.telegram_chat_id || "";
      inpMinDisc.value = settings.min_discount_pct || "20";
      inpMinProfit.value = settings.min_profit_tl || "350";
      inpAffTag.value = settings.amazon_affiliate_tag || "senintagin-21";
      inpHbAff.value = settings.hepsiburada_aff_id || "";
      if (inpIgUser) inpIgUser.value = settings.instagram_username || "@vurgunradari";
      if (inpIgPass && settings.instagram_password) inpIgPass.value = settings.instagram_password;
      if (chkIgAutopost) chkIgAutopost.checked = settings.instagram_auto_post === "1";
      settingsLoaded = true;
    }

    if (scanState && scanState.is_scanning) {
      scanStatusBadge.textContent = "🔄 Canlı Taranıyor...";
    } else if (scanState && scanState.last_scan_ts) {
      const dt = new Date(scanState.last_scan_ts * 1000);
      scanStatusBadge.textContent = "Son Tarama: " + dt.toLocaleTimeString("tr-TR");
    }
  }

  async function fetchState() {
    try {
      const resp = await fetch("/api/state?filter=" + encodeURIComponent(currentFilter));
      if (!resp.ok) return;
      const data = await resp.json();
      allDeals = data.deals || [];
      updateStats(allDeals, data.settings || {}, data.scan_state || {});
      renderDeals();
    } catch (_err) {
      // Ignore transient polling error
    }
  }

  async function sendDealToPhone(dealId) {
    try {
      const resp = await fetch("/api/notify-deal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deal_id: dealId }),
      });
      const data = await resp.json();
      if (data.ok) {
        showToast("📲 Fırsat ntfy.sh ile telefonuna gönderildi!");
      } else {
        showToast("Bildirim hatası: " + (data.error || "Bilinmeyen hata"));
      }
    } catch (_err) {
      showToast("Bağlantı hatası oluştu.");
    }
  }

  async function sendDealToTelegram(dealId) {
    try {
      const resp = await fetch("/api/telegram-deal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deal_id: dealId }),
      });
      const data = await resp.json();
      if (data.ok) {
        showToast("📢 Fırsat Telegram Kanalına başarıyla paylaşıldı!");
      } else {
        showToast("❌ Telegram Hatası: " + (data.error || "Ayarları kontrol et"));
      }
    } catch (_err) {
      showToast("Bağlantı hatası oluştu.");
    }
  }

  document.getElementById("btn-scan-now").addEventListener("click", async function () {
    showToast("⚡ Canlı tarama başlatıldı, Cimri ve Amazon TR taranıyor...");
    await fetch("/api/scan", { method: "POST" });
    setTimeout(fetchState, 1500);
  });

  document.getElementById("btn-test-ntfy").addEventListener("click", async function () {
    const topicVal = inpTopic.value.trim();
    showToast("📲 ntfy.sh kanalına test bildirimi gönderiliyor...");
    const resp = await fetch("/api/test-ntfy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ntfy_topic: topicVal }),
    });
    const data = await resp.json();
    if (data.ok) {
      showToast("✅ Test bildirimi gönderildi! ntfy uygulamasında '" + topicVal + "' kanalını kontrol et.");
      fetchState();
    } else {
      showToast("❌ Gönderilemedi: " + (data.error || "Hata"));
    }
  });

  document.getElementById("btn-test-tg").addEventListener("click", async function () {
    const tokVal = inpTgToken.value.trim();
    const chatVal = inpTgChat.value.trim();
    showToast("📢 Telegram Kanalına test paylaşımı gönderiliyor...");
    const resp = await fetch("/api/test-telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        telegram_bot_token: tokVal,
        telegram_chat_id: chatVal,
      }),
    });
    const data = await resp.json();
    if (data.ok) {
      showToast("🎉 Telegram Kanalına fırsat mesajı ve 'Hemen Kap' butonu atıldı!");
      fetchState();
    } else {
      showToast("❌ Telegram Hatası: " + (data.error || "Token ve Kanal ID kontrol et"));
    }
  });

  document.getElementById("btn-save-settings").addEventListener("click", async function () {
    const payload = {
      ntfy_topic: inpTopic.value.trim(),
      telegram_bot_token: inpTgToken.value.trim(),
      telegram_chat_id: inpTgChat.value.trim(),
      min_discount_pct: inpMinDisc.value.trim(),
      min_profit_tl: inpMinProfit.value.trim(),
      amazon_affiliate_tag: inpAffTag.value.trim(),
      hepsiburada_aff_id: inpHbAff.value.trim(),
      instagram_username: inpIgUser ? inpIgUser.value.trim() : "@vurgunradari",
      instagram_password: inpIgPass ? inpIgPass.value.trim() : "",
      instagram_auto_post: chkIgAutopost && chkIgAutopost.checked ? "1" : "0",
    };
    const resp = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (data.ok) {
      showToast("💾 Tüm ayarlar kaydedildi! Otomatik Telegram & ntfy radarı devrede.");
      settingsLoaded = false;
      fetchState();
    }
  });

  document.querySelectorAll(".tab-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".tab-btn").forEach(function (b) {
        b.classList.remove("active");
      });
      btn.classList.add("active");
      currentFilter = btn.getAttribute("data-filter") || "all";
      fetchState();
    });
  });

  inpSearch.addEventListener("input", function () {
    renderDeals();
  });

  fetchState();
  setInterval(fetchState, 6000);
})();
