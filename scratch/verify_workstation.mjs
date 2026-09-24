import fs from 'fs';
import path from 'path';

const ARTIFACT_DIR = 'C:/Users/vijay/.gemini/antigravity-ide/brain/c2b519c3-7e91-45a4-a863-7e5443210631';

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

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function run() {
  const tabsRes = await fetch('http://localhost:9222/json/list');
  const tabs = await tabsRes.json();
  const mainTab = tabs.find(t => t.url.includes('5173') || t.title.includes('Railway'));
  if (!mainTab) {
    console.error('Target tab not found:', tabs);
    process.exit(1);
  }

  const ws = new WebSocket(mainTab.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  console.log('Connected to CDP');

  await sendCDP(ws, 'Page.enable');
  await sendCDP(ws, 'Runtime.enable');

  // 1. Set Viewport 1920x1080
  await sendCDP(ws, 'Emulation.setDeviceMetricsOverride', {
    width: 1920,
    height: 1080,
    deviceScaleFactor: 1,
    mobile: false
  });

  // Reload
  await sendCDP(ws, 'Page.navigate', { url: 'http://localhost:5173/' });
  await sleep(4000);

  // Capture Default Matrix
  let shot = await sendCDP(ws, 'Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'final_workstation_1920x1080.png'), Buffer.from(shot.data, 'base64'));
  console.log('Saved final_workstation_1920x1080.png');

  // 2. Click Block BP-001
  await sendCDP(ws, 'Runtime.evaluate', {
    expression: `
      const blk = document.querySelector('[id*="matrix-block-"]') || document.querySelector('[data-block-code]');
      if (blk) blk.click();
    `
  });
  await sleep(600);
  shot = await sendCDP(ws, 'Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'final_block_inspected_1920.png'), Buffer.from(shot.data, 'base64'));
  console.log('Saved final_block_inspected_1920.png');

  // 3. Click Train 20665 or any train
  await sendCDP(ws, 'Runtime.evaluate', {
    expression: `
      const tr = document.getElementById('matrix-train-20665') || document.querySelector('[id*="matrix-train-"]');
      if (tr) tr.click();
    `
  });
  await sleep(600);
  shot = await sendCDP(ws, 'Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'final_train_inspected_1920.png'), Buffer.from(shot.data, 'base64'));
  console.log('Saved final_train_inspected_1920.png');

  // 4. Click Feasible Window
  await sendCDP(ws, 'Runtime.evaluate', {
    expression: `
      const win = document.querySelector('[id*="matrix-win-"]');
      if (win) win.click();
    `
  });
  await sleep(600);
  shot = await sendCDP(ws, 'Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'final_window_inspected_1920.png'), Buffer.from(shot.data, 'base64'));
  console.log('Saved final_window_inspected_1920.png');

  // 5. Open Safety Check Validator Modal
  await sendCDP(ws, 'Runtime.evaluate', {
    expression: `
      const safetyBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText && b.innerText.includes('SAFETY CHECK'));
      if (safetyBtn) safetyBtn.click();
    `
  });
  await sleep(700);
  shot = await sendCDP(ws, 'Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'final_safety_modal_1920.png'), Buffer.from(shot.data, 'base64'));
  console.log('Saved final_safety_modal_1920.png');

  // Close modal by clicking Close button or Acknowledge & Close
  await sendCDP(ws, 'Runtime.evaluate', {
    expression: `
      const closeBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText && (b.innerText.includes('Acknowledge') || b.innerText.includes('Close')));
      if (closeBtn) closeBtn.click();
    `
  });
  await sleep(600);

  // 6. Test 1440x900
  await sendCDP(ws, 'Emulation.setDeviceMetricsOverride', {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false
  });
  await sleep(800);
  shot = await sendCDP(ws, 'Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'final_workstation_1440x900.png'), Buffer.from(shot.data, 'base64'));
  console.log('Saved final_workstation_1440x900.png');

  // 7. Test 1366x768
  await sendCDP(ws, 'Emulation.setDeviceMetricsOverride', {
    width: 1366,
    height: 768,
    deviceScaleFactor: 1,
    mobile: false
  });
  await sleep(800);
  shot = await sendCDP(ws, 'Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'final_workstation_1366x768.png'), Buffer.from(shot.data, 'base64'));
  console.log('Saved final_workstation_1366x768.png');

  // Reset to 1920x1080
  await sendCDP(ws, 'Emulation.setDeviceMetricsOverride', {
    width: 1920,
    height: 1080,
    deviceScaleFactor: 1,
    mobile: false
  });

  ws.close();
  console.log('Verification finished successfully.');
}

run().catch(console.error);
