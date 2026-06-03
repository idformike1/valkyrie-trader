const puppeteer = require('puppeteer-core');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true
  });
  
  const page = await browser.newPage();
  await page.goto('http://localhost:3000/');
  
  // Wait 5 seconds to ensure Next.js hydration is fully completed!
  console.log("Waiting 5 seconds for Next.js hydration...");
  await new Promise(resolve => setTimeout(resolve, 5000));

  const result = await page.evaluate(() => {
    const spans = Array.from(document.querySelectorAll('span.truncate.uppercase.font-medium'));
    const bankniftySpan = spans.find(s => s.textContent === 'BANKNIFTY');
    if (!bankniftySpan) return "Error: Span not found";
    
    let clickEl = bankniftySpan;
    const path = [];
    while (clickEl) {
      path.push({
        tag: clickEl.tagName,
        className: clickEl.className
      });
      if (clickEl.className && typeof clickEl.className === 'string' && clickEl.className.includes('cursor-pointer')) {
        break;
      }
      clickEl = clickEl.parentElement;
    }
    
    if (clickEl) {
      clickEl.click();
      return { status: "Clicked", path };
    }
    return { status: "Click target not found", path };
  });

  console.log("Result:", result);
  
  // Wait 2 seconds and check local storage
  await new Promise(resolve => setTimeout(resolve, 2000));
  const storage = await page.evaluate(() => {
    return localStorage.getItem('valkyrie-terminal-context-storage');
  });
  console.log("Storage after click:", storage);

  await browser.close();
})();
