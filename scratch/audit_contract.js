const puppeteer = require('puppeteer-core');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true
  });
  
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });
  await page.goto('http://localhost:3000/');
  
  // Wait for the workspace to load
  await page.waitForSelector('select');
  
  // Wait for BANKNIFTY selector to load
  await page.waitForFunction(() => {
    const spans = Array.from(document.querySelectorAll('span'));
    return spans.some(s => s.textContent === 'BANKNIFTY');
  }, { timeout: 10000 });
  
  // Click BANKNIFTY
  await page.evaluate(() => {
    const spans = Array.from(document.querySelectorAll('span'));
    const span = spans.find(s => {
      if (s.textContent !== 'BANKNIFTY') return false;
      let el = s;
      while (el) {
        if (el.className && typeof el.className === 'string' && el.className.includes('cursor-pointer')) {
          return true;
        }
        el = el.parentElement;
      }
      return false;
    });
    if (span) {
      let clickEl = span;
      while (clickEl) {
        if (clickEl.className && typeof clickEl.className === 'string' && clickEl.className.includes('cursor-pointer')) {
          break;
        }
        clickEl = clickEl.parentElement;
      }
      if (clickEl) clickEl.click();
    }
  });
  
  // Wait for option chain strikes (any tbody row)
  await page.waitForSelector('tbody tr', { timeout: 15000 });
  
  // Click the CE button of the first row
  await page.evaluate(() => {
    const rowEl = document.querySelector('tbody tr');
    if (rowEl) {
      const buttons = Array.from(rowEl.querySelectorAll('button'));
      const ceButton = buttons.find(b => b.textContent && b.textContent.includes('CE'));
      if (ceButton) ceButton.click();
    }
  });
  
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Dump localStorage selectedInstrument
  const storeStr = await page.evaluate(() => localStorage.getItem('valkyrie-terminal-context-storage'));
  const store = storeStr ? JSON.parse(storeStr) : null;
  const selectedInstrument = store ? store.state.selectedInstrument : null;
  
  console.log("=================== SELECTED INSTRUMENT OBJECT DUMP ===================");
  console.log(JSON.stringify(selectedInstrument, null, 2));
  console.log("=======================================================================");
  
  await browser.close();
})();
