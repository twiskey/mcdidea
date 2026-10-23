const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  page.on('console', m => { if (m.type() === 'error') console.log('CONSOLE-ERR:', m.text()); });
  page.on('pageerror', e => console.log('PAGE-ERR:', e.message));

  await page.goto('http://127.0.0.1:8765/', { waitUntil: 'networkidle' });

  const bar = await page.locator('.cartbar').boundingBox();
  console.log('cartbar box:', JSON.stringify(bar));

  // 加三件商品（先切到对应分类）
  await page.locator('.item[data-code="1406"] .step-btn.add').click();
  await page.locator('#tabs .tab[data-cat="side"]').click();
  await page.locator('.item[data-code="4437"] .step-btn.add').click();
  await page.locator('#tabs .tab[data-cat="drink"]').click();
  await page.locator('.item[data-code="3755"] .step-btn.add').click();
  await page.waitForTimeout(200);
  console.log('cart:', await page.locator('#cartCount').textContent(), await page.locator('#cartTotal').textContent());
  await page.screenshot({ path: 'out/shot_menu_cart.png' });

  // 下单
  await page.locator('#btnOrder').click();
  await page.waitForSelector('#view-pickup.is-active');
  await page.waitForTimeout(400);
  console.log('pickup:', await page.locator('#pickupNo').textContent());
  await page.screenshot({ path: 'out/shot_pickup.png' });

  // 想看 → 光谱页
  await page.locator('#btnYes').click();
  await page.waitForSelector('#view-portrait.is-active');
    await page.waitForFunction(() => {
    const img = document.getElementById('spectrumImg');
    return img.complete && img.naturalWidth > 0;
  }, { timeout: 30000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: 'out/shot_portrait_top.png' });
  console.log('lead:', (await page.locator('#plain p.lead').textContent()).slice(0, 40));
  console.log('sign:', await page.locator('.sign').textContent());
  console.log('share btn visible:', await page.locator('#btnShare').isVisible());
  console.log('pro block count (should be 0):', await page.locator('details.pro').count());
  await page.locator('.melody-card').scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await page.screenshot({ path: 'out/shot_portrait_melody.png' });

  // 放大光谱：整图必须落在视口内（不出现横向/纵向滚动）
  await page.locator('#btnZoom').click();
  await page.waitForSelector('#lightbox:not([hidden])');
  await page.waitForTimeout(300);
  const fit = await page.evaluate(() => {
    const img = document.getElementById('lbImg').getBoundingClientRect();
    const box = document.getElementById('lightbox');
    return { iw: Math.round(img.width), ih: Math.round(img.height),
             vw: innerWidth, vh: innerHeight,
             scrollW: box.scrollWidth, scrollH: box.scrollHeight,
             natW: document.getElementById('lbImg').naturalWidth };
  });
  console.log('lightbox fit:', JSON.stringify(fit));
  const fits = fit.iw <= fit.vw + 1 && fit.ih <= fit.vh + 1
    && fit.scrollW <= fit.vw + 1 && fit.scrollH <= fit.vh + 1;
  console.log('lightbox fits viewport:', fits, '| original kept:', fit.natW);
  await page.screenshot({ path: 'out/shot_lightbox.png' });
  await page.locator('#lbClose').click();

  // 横屏再验一次
  await page.setViewportSize({ width: 844, height: 390 });
  await page.locator('#btnZoom').click();
  await page.waitForTimeout(300);
  const land = await page.evaluate(() => {
    const r = document.getElementById('lbImg').getBoundingClientRect();
    return { iw: Math.round(r.width), ih: Math.round(r.height), vw: innerWidth, vh: innerHeight };
  });
  console.log('landscape fit:', JSON.stringify(land),
              '=>', land.iw <= land.vw + 1 && land.ih <= land.vh + 1);
  await page.screenshot({ path: 'out/shot_lightbox_landscape.png' });
  await page.locator('#lbClose').click();
  await page.setViewportSize({ width: 390, height: 844 });

  // 切摇滚
  await page.locator('.seg-btn[data-style="rock"]').click();
  await page.waitForFunction(() => document.querySelectorAll('.seg-btn:not([disabled])').length === 3, { timeout: 30000 });
  await page.waitForFunction(() => {
    const img = document.getElementById('spectrumImg');
    const a = document.getElementById('audio');
    return img.complete && a.src.includes('rock');
  }, { timeout: 30000 });
  console.log('rock switch ok');
  await browser.close();
  console.log('FLOW OK');
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
