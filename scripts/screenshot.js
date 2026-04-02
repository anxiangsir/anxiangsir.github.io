const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/usr/bin/google-chrome' });
  
  // Phone viewport
  const pagePhone = await browser.newPage({ viewport: { width: 375, height: 812 } });
  await pagePhone.goto('file:///ov2/xiangan/anxiangsir.github.io/partial_fc.html');
  // Wait a moment for animations
  await pagePhone.waitForTimeout(1000);
  await pagePhone.screenshot({ path: 'screenshot_phone.png', fullPage: true });
  await pagePhone.close();

  // Tablet viewport
  const pageTablet = await browser.newPage({ viewport: { width: 768, height: 1024 } });
  await pageTablet.goto('file:///ov2/xiangan/anxiangsir.github.io/partial_fc.html');
  await pageTablet.waitForTimeout(1000);
  await pageTablet.screenshot({ path: 'screenshot_tablet.png', fullPage: true });
  await pageTablet.close();

  await browser.close();
  console.log('Screenshots saved as screenshot_phone.png and screenshot_tablet.png');
})();