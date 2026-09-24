import fs from 'fs';

async function sendCDP(ws, method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = Math.floor(Math.random() * 1000000);
    const handler = (event) => {
      const resp = JSON.parse(event.data);
      if (resp.id === id) {
        ws.removeEventListener('message', handler);
        if (resp.error) reject(resp.error);
        else resolve(resp.result);
      }
    };
    ws.addEventListener('message', handler);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function run() {
  const tabsRes = await fetch('http://localhost:9222/json/list');
  const tabs = await tabsRes.json();
  const mainTab = tabs.find(t => t.url.includes('5173') || t.title.includes('Railway'));
  const ws = new WebSocket(mainTab.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);

  await sendCDP(ws, 'Emulation.setDeviceMetricsOverride', {
    width: 1366,
    height: 768,
    deviceScaleFactor: 1,
    mobile: false
  });

  const res = await sendCDP(ws, 'Runtime.evaluate', {
    expression: `
      (() => {
        const body = document.body;
        const root = document.getElementById('root');
        const main = document.querySelector('main');
        const aside = document.querySelector('aside');
        const btn = Array.from(document.querySelectorAll('button')).find(el => el.innerText && el.innerText.includes('RE-OPTIMIZE'));
        const parentConsole = btn ? btn.closest('div[class*="border-t"]') : null;
        
        const ancestors = [];
        let curr = parentConsole;
        while (curr && curr !== document.body) {
          ancestors.push({
            tag: curr.tagName,
            className: curr.className.slice(0, 50),
            scrollHeight: curr.scrollHeight,
            clientHeight: curr.clientHeight,
            offsetHeight: curr.offsetHeight,
            overflow: window.getComputedStyle(curr).overflowY
          });
          curr = curr.parentElement;
        }

        return {
          windowInnerHeight: window.innerHeight,
          btnRect: btn ? { top: btn.getBoundingClientRect().top, bottom: btn.getBoundingClientRect().bottom } : null,
          ancestors
        };
      })()
    `,
    returnByValue: true
  });

  console.log(JSON.stringify(res.result.value, null, 2));
  ws.close();
}

run().catch(console.error);
